"""
Toggle Status Checker
Logs in once and checks the current state of toggles for all URLs.
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


class StatusChecker:
    def __init__(self, excel_path: str, headless: bool = True):
        self.excel_path = excel_path
        self.headless = headless
        self.results = []

    def load_excel(self) -> pd.DataFrame:
        """Load and validate Excel file."""
        logger.info(f"Loading Excel file: {self.excel_path}")

        df = pd.read_excel(self.excel_path)
        df.columns = df.columns.str.strip().str.lower()

        required_columns = ['url', 'userid', 'password']
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            raise ValueError(f"Missing required columns: {missing}")

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

            logger.info("Login successful")
            return True

        except Exception as e:
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
                logger.info("Removed Pendo elements via JavaScript")
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

    def run(self):
        """Main execution method."""
        df = self.load_excel()

        if len(df) == 0:
            logger.info("No URLs found in Excel")
            return

        logger.info(f"Checking status for {len(df)} URLs")

        with sync_playwright() as p:
            # Launch browser
            browser = None

            try:
                browser = p.chromium.launch(headless=self.headless)
            except Exception:
                pass

            if not browser:
                try:
                    browser = p.chromium.launch(headless=self.headless, channel="chrome")
                except Exception:
                    pass

            if not browser:
                try:
                    browser = p.firefox.launch(headless=self.headless)
                except Exception:
                    pass

            if not browser:
                logger.error("No browser available")
                return

            # Create single context for session sharing
            context = browser.new_context()

            # Step 1: Login using first URL
            first_row = df.iloc[0]
            logger.info(f"\n{'='*50}")
            logger.info("Step 1: Logging in...")

            first_page = context.new_page()
            first_page.goto(first_row['url'], wait_until="networkidle", timeout=30000)

            if self.is_login_page(first_page):
                if not self.login(first_page, first_row['userid'], first_row['password']):
                    logger.error("Login failed, aborting")
                    context.close()
                    browser.close()
                    return

                # Navigate back to first URL
                first_page.goto(first_row['url'], wait_until="domcontentloaded", timeout=30000)
                first_page.wait_for_load_state("networkidle", timeout=30000)

            logger.info("Session established")

            # Step 2: Open all URLs in tabs
            logger.info(f"\n{'='*50}")
            logger.info(f"Step 2: Opening {len(df)} tabs...")

            pages = [first_page]
            urls = [first_row['url']]

            for idx in range(1, len(df)):
                row = df.iloc[idx]
                logger.info(f"Opening tab {idx + 1}: {row['url'].split('/')[-1]}")

                page = context.new_page()
                page.goto(row['url'], wait_until="domcontentloaded", timeout=30000)
                pages.append(page)
                urls.append(row['url'])

            # Wait for all tabs to load
            logger.info("Waiting for tabs to load...")
            for page in pages:
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

            # Step 3: Check status of each tab
            logger.info(f"\n{'='*50}")
            logger.info("Step 3: Checking toggle status...")

            for idx, (page, url) in enumerate(zip(pages, urls)):
                url_short = url.split('/')[-1]
                logger.info(f"Checking {idx + 1}/{len(pages)}: {url_short}")

                page.bring_to_front()
                page.wait_for_timeout(500)

                result = self.check_toggle_status(page, url)
                self.results.append(result)

                logger.info(f"  Status: {result['toggle_status']}")

                page.close()

            context.close()
            browser.close()

        self.save_results()
        self.print_summary()

    def save_results(self):
        """Save results to Excel (overwrites previous file)."""
        output_file = "status_report.xlsx"
        results_df = pd.DataFrame(self.results)
        results_df.to_excel(output_file, index=False)
        logger.info(f"Results saved to: {output_file}")

    def print_summary(self):
        """Print status summary."""
        logger.info("\n" + "="*50)
        logger.info("TOGGLE STATUS REPORT")
        logger.info("="*50)

        on_count = sum(1 for r in self.results if r['toggle_status'] == 'ON')
        off_count = sum(1 for r in self.results if r['toggle_status'] == 'OFF')
        error_count = sum(1 for r in self.results if r['toggle_status'] in ['ERROR', 'NOT_FOUND', 'UNKNOWN'])

        logger.info(f"Total URLs: {len(self.results)}")
        logger.info(f"Toggle ON:  {on_count}")
        logger.info(f"Toggle OFF: {off_count}")
        logger.info(f"Errors:     {error_count}")

        logger.info("\nDETAILED STATUS:")
        logger.info("-" * 40)
        for r in self.results:
            status_icon = "✓" if r['toggle_status'] == 'ON' else "✗" if r['toggle_status'] == 'OFF' else "?"
            logger.info(f"  [{status_icon}] {r['toggle_status']:8} | {r['url_short']}")


def main():
    parser = argparse.ArgumentParser(description='Check Toggle Status')
    parser.add_argument('excel_file', help='Path to Excel file with URLs and credentials')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode')
    parser.add_argument('--no-headless', action='store_false', dest='headless',
                        help='Run browser with visible window')

    args = parser.parse_args()

    if not Path(args.excel_file).exists():
        logger.error(f"Excel file not found: {args.excel_file}")
        return

    checker = StatusChecker(args.excel_file, args.headless)
    checker.run()


if __name__ == "__main__":
    main()
