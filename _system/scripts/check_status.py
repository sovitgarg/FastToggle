"""
Toggle Status Checker
Logs in once and checks the current state of toggles for all URLs.
Uses batch processing for reliability with large number of URLs.
Outputs results to Excel file.

Excel format:
URL | userid | password

Usage:
python check_status.py "ToggleExcel_A.xlsx" --no-headless
python check_status.py "ToggleExcel_B.xlsx" --no-headless
"""

import pandas as pd
from playwright.sync_api import sync_playwright
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'status_check_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Batch size for processing URLs
BATCH_SIZE = 5


def print_status(message, symbol="*"):
    """Print user-friendly status message."""
    print(f"\n{symbol * 3} {message} {symbol * 3}")


def print_progress(current, total, url_name, status=""):
    """Print progress indicator."""
    percentage = int((current / total) * 100)
    bar_length = 30
    filled = int(bar_length * current / total)
    bar = "=" * filled + "-" * (bar_length - filled)
    status_text = f" - {status}" if status else ""
    print(f"\r[{bar}] {current}/{total} ({percentage}%) | {url_name}{status_text}    ", end="", flush=True)


class StatusChecker:
    def __init__(self, excel_path: str, headless: bool = True):
        self.excel_path = excel_path
        self.headless = headless
        self.results = []
        self.context = None
        self.browser = None

    def load_excel(self) -> pd.DataFrame:
        """Load and validate Excel file."""
        print_status(f"Loading Excel file: {self.excel_path}", ">>")

        df = pd.read_excel(self.excel_path)
        df.columns = df.columns.str.strip().str.lower()

        required_columns = ['url', 'userid', 'password']
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Clean data: remove empty rows and whitespace
        df = df.dropna(subset=['url'])
        df['url'] = df['url'].astype(str).str.strip()
        df = df[df['url'] != '']
        df = df[~df['url'].str.lower().isin(['nan', 'none', ''])]

        # Reset index after filtering
        df = df.reset_index(drop=True)

        print(f"    Found {len(df)} URLs to check")
        logger.info(f"Loaded {len(df)} rows from Excel")
        return df

    def is_login_page(self, page) -> bool:
        """Detect if the current page is a login page."""
        login_indicators = [
            'input[type="password"]',
            'form[action*="login"]',
            'form[action*="signin"]',
        ]

        for selector in login_indicators:
            try:
                if page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue

        return False

    def login(self, page, userid: str, password: str) -> bool:
        """Login to the website."""
        try:
            print(f"    Logging in as: {userid}")
            logger.info(f"Attempting login for user: {userid}")

            username_selectors = [
                'input[placeholder*="email"]',
                'input[placeholder*="Email"]',
                'input[type="email"]',
                'input[name="email"]',
            ]

            password_selectors = [
                'input[placeholder*="password"]',
                'input[type="password"]',
            ]

            submit_selectors = [
                'button:has-text("Login")',
                'button:has-text("Log in")',
                'button[type="submit"]',
            ]

            # Fill username
            for selector in username_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.fill(selector, userid)
                        break
                except Exception:
                    continue

            # Fill password
            for selector in password_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.fill(selector, password)
                        break
                except Exception:
                    continue

            # Click submit
            for selector in submit_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.click(selector)
                        break
                except Exception:
                    continue

            # Wait for login to complete
            page.wait_for_timeout(3000)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            print("    Login successful!")
            logger.info("Login successful")
            return True

        except Exception as e:
            print(f"    Login FAILED: {str(e)}")
            logger.error(f"Login failed: {str(e)}")
            return False

    def dismiss_popups(self, page):
        """Dismiss Pendo popups and other overlays that may block interactions."""
        try:
            # Pendo popup dismiss selectors
            pendo_dismiss_selectors = [
                '#pendo-close-guide-.*',
                '[data-pendo-close-guide]',
                'button._pendo-close-guide',
                '._pendo-close-guide',
                '[class*="pendo"] button[aria-label*="close"]',
                '[class*="pendo"] button[aria-label*="Close"]',
                '[class*="pendo"] [class*="close"]',
                '#pendo-base button',
                '._pendo-step-container button',
            ]

            for selector in pendo_dismiss_selectors:
                try:
                    close_btn = page.locator(selector).first
                    if close_btn.count() > 0 and close_btn.is_visible():
                        close_btn.click(force=True)
                        logger.info(f"Dismissed Pendo popup using: {selector}")
                        page.wait_for_timeout(500)
                        return True
                except Exception:
                    continue

            # Try pressing Escape key to dismiss any modal
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                pass

            # Try removing Pendo elements via JavaScript
            try:
                page.evaluate("""
                    const pendoElements = document.querySelectorAll('#pendo-base, [class*="pendo-backdrop"], ._pendo-step-container');
                    pendoElements.forEach(el => el.remove());
                """)
            except Exception:
                pass

            return False
        except Exception as e:
            logger.debug(f"Error dismissing popups: {str(e)}")
            return False

    def check_toggle_status(self, page, url: str) -> dict:
        """Check the current toggle status without modifying it."""
        result = {
            'url': url,
            'url_short': url.split('/')[-1],
            'toggle_status': 'UNKNOWN',
            'message': '',
            'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            # Wait for page to fully load
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                logger.info("Page still loading, continuing...")
            page.wait_for_timeout(3000)

            # Dismiss any Pendo popups that may be blocking
            self.dismiss_popups(page)

            # Check toggle state
            toggle_selector = 'text="In-app event postbacks" >> .. >> input[type="checkbox"]'

            # Wait for toggle element to appear with retry logic
            toggle_found = False
            for attempt in range(2):
                try:
                    page.wait_for_selector(toggle_selector, timeout=20000)
                    toggle_found = True
                    break
                except Exception:
                    if attempt == 0:
                        logger.info("Toggle not found, refreshing page and retrying...")
                        page.reload(wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(3000)
                        self.dismiss_popups(page)
                    else:
                        logger.info("Toggle not found after retry")

            if not toggle_found:
                result['toggle_status'] = 'NOT_FOUND'
                result['message'] = 'Toggle element not found (timeout waiting for element after retry)'
                return result

            toggle = page.locator(toggle_selector).first

            if toggle.count() > 0:
                is_checked = toggle.is_checked()
                result['toggle_status'] = 'ON' if is_checked else 'OFF'
                result['message'] = 'Status checked successfully'
            else:
                result['toggle_status'] = 'NOT_FOUND'
                result['message'] = 'Toggle element not found on page'

        except Exception as e:
            result['toggle_status'] = 'ERROR'
            result['message'] = str(e)
            logger.error(f"Error checking {url}: {str(e)}")

        return result

    def process_batch(self, df_batch, batch_num, total_batches, start_idx, total_urls):
        """Process a batch of URLs."""
        print(f"\n    Processing batch {batch_num}/{total_batches} ({len(df_batch)} URLs)...")

        pages = []
        urls = []
        processed_count = 0

        # Open all URLs in this batch
        for batch_idx, (idx, row) in enumerate(df_batch.iterrows()):
            url_short = row['url'].split('/')[-1]
            current_num = start_idx + batch_idx + 1
            print_progress(current_num, total_urls, url_short, "Opening...")

            try:
                page = self.context.new_page()
                page.goto(row['url'], wait_until="domcontentloaded", timeout=120000)
                pages.append(page)
                urls.append(row['url'])
                logger.info(f"Opened: {url_short}")
            except Exception as e:
                # If page fails to open, record error and continue
                logger.error(f"Failed to open {url_short}: {str(e)}")
                self.results.append({
                    'url': row['url'],
                    'url_short': url_short,
                    'toggle_status': 'ERROR',
                    'message': f'Failed to open page: {str(e)[:100]}',
                    'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                processed_count += 1
                continue

        # Wait for all pages to load
        if pages:
            print(f"\n    Waiting for {len(pages)} pages to load...")
            for page in pages:
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass

        # Check status of each page
        for idx, (page, url) in enumerate(zip(pages, urls)):
            url_short = url.split('/')[-1]
            current_num = start_idx + processed_count + idx + 1
            print_progress(current_num, total_urls, url_short, "Checking...")

            try:
                page.bring_to_front()
                page.wait_for_timeout(500)

                result = self.check_toggle_status(page, url)
                self.results.append(result)

                status_symbol = result['toggle_status']
                print_progress(current_num, total_urls, url_short, status_symbol)
                logger.info(f"Status for {url_short}: {result['toggle_status']}")

            except Exception as e:
                logger.error(f"Error checking {url_short}: {str(e)}")
                self.results.append({
                    'url': url,
                    'url_short': url_short,
                    'toggle_status': 'ERROR',
                    'message': f'Error: {str(e)[:100]}',
                    'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            finally:
                try:
                    page.close()
                except Exception:
                    pass

        print()  # New line after progress bar

    def run(self):
        """Main execution method with batch processing."""
        df = self.load_excel()

        if len(df) == 0:
            print_status("No URLs found in Excel file!", "!!")
            return

        total_urls = len(df)
        total_batches = (total_urls + BATCH_SIZE - 1) // BATCH_SIZE

        print_status(f"STATUS CHECK - Checking {total_urls} URLs", "=")
        print(f"    Processing in {total_batches} batches of up to {BATCH_SIZE} URLs each")

        try:
            with sync_playwright() as p:
                # Launch browser
                print_status("Starting browser...", ">>")
                browser_name = None

                try:
                    self.browser = p.chromium.launch(headless=self.headless)
                    browser_name = "Chromium"
                except Exception:
                    pass

                if not self.browser:
                    try:
                        self.browser = p.chromium.launch(headless=self.headless, channel="chrome")
                        browser_name = "Chrome"
                    except Exception:
                        pass

                if not self.browser:
                    try:
                        self.browser = p.firefox.launch(headless=self.headless)
                        browser_name = "Firefox"
                    except Exception:
                        pass

                if not self.browser:
                    print_status("ERROR: No browser available!", "!!")
                    logger.error("No browser available")
                    return

                print(f"    Using: {browser_name}")
                logger.info(f"Using browser: {browser_name}")

                # Create single context (session) for all operations
                self.context = self.browser.new_context()

                # Step 1: Login using first URL
                print_status("Step 1: Logging in...", ">>")
                first_row = df.iloc[0]

                first_page = self.context.new_page()
                try:
                    first_page.goto(first_row['url'], wait_until="domcontentloaded", timeout=120000)
                    first_page.wait_for_load_state("networkidle", timeout=30000)
                except Exception as e:
                    logger.info(f"Page load timeout, continuing: {str(e)}")

                if self.is_login_page(first_page):
                    if not self.login(first_page, first_row['userid'], first_row['password']):
                        print_status("Login FAILED! Please check credentials.", "!!")
                        self.context.close()
                        self.browser.close()
                        return
                else:
                    print("    Already logged in (session active)")

                first_page.close()
                print_status("Login complete - Session established", "OK")

                # Step 2: Process URLs in batches
                print_status(f"Step 2: Checking {total_urls} URLs in batches...", ">>")

                for batch_num in range(total_batches):
                    start_idx = batch_num * BATCH_SIZE
                    end_idx = min(start_idx + BATCH_SIZE, total_urls)
                    df_batch = df.iloc[start_idx:end_idx]

                    self.process_batch(df_batch, batch_num + 1, total_batches, start_idx, total_urls)

                self.context.close()
                self.browser.close()

        except Exception as e:
            print_status(f"UNEXPECTED ERROR: {str(e)}", "!!")
            logger.error(f"Unexpected error: {str(e)}")
            # Try to close browser on error
            try:
                if self.context:
                    self.context.close()
                if self.browser:
                    self.browser.close()
            except Exception:
                pass
        finally:
            # Always save results, even if there was an error
            self.save_results()
            self.print_summary()

    def save_results(self):
        """Save results to Excel (overwrites previous file)."""
        if not self.results:
            print_status("No results to save", "!!")
            return

        output_file = "status_report.xlsx"
        results_df = pd.DataFrame(self.results)
        results_df.to_excel(output_file, index=False)

        print_status(f"Results saved to: {output_file}", ">>")
        logger.info(f"Results saved to: {output_file}")

    def print_summary(self):
        """Print status summary."""
        if not self.results:
            return

        on_count = sum(1 for r in self.results if r['toggle_status'] == 'ON')
        off_count = sum(1 for r in self.results if r['toggle_status'] == 'OFF')
        error_count = sum(1 for r in self.results if r['toggle_status'] in ['ERROR', 'NOT_FOUND', 'UNKNOWN'])

        print("\n")
        print("=" * 60)
        print("                  TOGGLE STATUS REPORT")
        print("=" * 60)
        print(f"  Total URLs:  {len(self.results)}")
        print(f"  Toggle ON:   {on_count}")
        print(f"  Toggle OFF:  {off_count}")
        print(f"  Errors:      {error_count}")
        print("=" * 60)

        if error_count > 0:
            print("\n  ISSUES FOUND:")
            print("-" * 60)
            for r in self.results:
                if r['toggle_status'] in ['ERROR', 'NOT_FOUND', 'UNKNOWN']:
                    print(f"  [?] {r['url_short']}")
                    print(f"      {r['message'][:50]}...")
            print("-" * 60)

        print(f"\n  Output file: status_report.xlsx")
        print("=" * 60)

        logger.info(f"Summary - Total: {len(self.results)}, ON: {on_count}, OFF: {off_count}, Errors: {error_count}")


def main():
    print("\n")
    print("=" * 60)
    print("        TOGGLE STATUS CHECKER")
    print("=" * 60)

    parser = argparse.ArgumentParser(description='Check Toggle Status')
    parser.add_argument('excel_file', help='Path to Excel file with URLs and credentials')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode')
    parser.add_argument('--no-headless', action='store_false', dest='headless',
                        help='Run browser with visible window')

    args = parser.parse_args()

    if not Path(args.excel_file).exists():
        print_status(f"ERROR: Excel file not found: {args.excel_file}", "!!")
        return

    try:
        checker = StatusChecker(args.excel_file, args.headless)
        checker.run()
    except Exception as e:
        print_status(f"FATAL ERROR: {str(e)}", "!!")
        logger.error(f"Fatal error: {str(e)}")

    print("\nPress Enter to close...")
    try:
        input()
    except Exception:
        pass


if __name__ == "__main__":
    main()
