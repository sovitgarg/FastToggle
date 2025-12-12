"""
Automated Toggle Script
Reads URLs from Excel and toggles settings on each website.
Uses single login session with multiple tabs for efficiency.

Excel format:
URL | Toggle | userid | password
https://example.com/settings | Yes | user1 | pass1
https://example.com/settings | No | user2 | pass2
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
        logging.FileHandler(f'toggle_automation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ToggleAutomation:
    def __init__(self, excel_path: str, headless: bool = True):
        self.excel_path = excel_path
        self.headless = headless
        self.results = []

    def load_excel(self) -> pd.DataFrame:
        """Load and validate Excel file."""
        logger.info(f"Loading Excel file: {self.excel_path}")

        df = pd.read_excel(self.excel_path)
        df.columns = df.columns.str.strip().str.lower()

        required_columns = ['url', 'toggle', 'userid', 'password']
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df['toggle'] = df['toggle'].str.strip().str.lower()

        logger.info(f"Loaded {len(df)} rows from Excel")
        return df

    def is_login_page(self, page) -> bool:
        """Detect if the current page is a login page."""
        login_indicators = [
            'input[type="password"]',
            'form[action*="login"]',
            'form[action*="signin"]',
            'form[action*="auth"]',
            '#login-form',
            '.login-form',
        ]

        for selector in login_indicators:
            try:
                if page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue

        return False

    def login(self, page, userid: str, password: str) -> bool:
        """Login to the website. Optimized for AppsFlyer."""
        try:
            logger.info(f"Attempting login for user: {userid}")

            username_selectors = [
                'input[placeholder*="email"]',
                'input[placeholder*="Email"]',
                'input[type="email"]',
                'input[name="email"]',
                'input[name="username"]',
            ]

            password_selectors = [
                'input[placeholder*="password"]',
                'input[placeholder*="Password"]',
                'input[type="password"]',
            ]

            submit_selectors = [
                'button:has-text("Login")',
                'button:has-text("Log in")',
                'button:has-text("Sign in")',
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

    def toggle_and_verify(self, page, url: str) -> dict:
        """Toggle the setting and verify the result."""
        result = {
            'url': url,
            'status': 'failed',
            'toggle_state_before': 'UNKNOWN',
            'toggle_state_after': 'UNKNOWN',
            'message': '',
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            # Wait for page to fully load
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(2000)

            # Check state before toggle
            toggle_selector = 'text="In-app event postbacks" >> .. >> input[type="checkbox"]'
            toggle = page.locator(toggle_selector).first

            if toggle.count() == 0:
                result['message'] = 'Toggle element not found'
                return result

            state_before = toggle.is_checked()
            result['toggle_state_before'] = 'ON' if state_before else 'OFF'
            logger.info(f"Toggle state before: {result['toggle_state_before']}")

            # Click toggle
            page.click(toggle_selector)
            logger.info("Toggle clicked")

            # Wait for UI update
            page.wait_for_timeout(500)

            # Click save
            save_selectors = [
                'button:has-text("Save Integration")',
                'button:has-text("Save")',
            ]

            saved = False
            for selector in save_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.click(selector)
                        saved = True
                        logger.info(f"Save clicked")
                        break
                except Exception:
                    continue

            if not saved:
                result['message'] = 'Save button not found'
                return result

            # Wait for save to complete
            page.wait_for_load_state("networkidle", timeout=10000)
            page.wait_for_timeout(3000)

            # Verify state after save
            state_after = page.locator(toggle_selector).first.is_checked()
            result['toggle_state_after'] = 'ON' if state_after else 'OFF'
            logger.info(f"Toggle state after: {result['toggle_state_after']}")

            # Determine success based on state change
            if state_before != state_after:
                result['status'] = 'success'
                result['message'] = f'Toggle changed from {result["toggle_state_before"]} to {result["toggle_state_after"]}'
            else:
                result['status'] = 'failed'
                result['message'] = f'Toggle state unchanged: {result["toggle_state_after"]}'

        except Exception as e:
            result['status'] = 'error'
            result['message'] = str(e)
            logger.error(f"Error: {str(e)}")

        return result

    def run(self):
        """Main execution method using tabs."""
        df = self.load_excel()

        # Filter rows where toggle is 'yes'
        active_rows = df[df['toggle'] == 'yes'].reset_index(drop=True)

        if len(active_rows) == 0:
            logger.info("No rows with Toggle=Yes found")
            return

        logger.info(f"Processing {len(active_rows)} URLs with Toggle=Yes")

        with sync_playwright() as p:
            # Launch browser
            browser = None
            browser_name = None

            try:
                browser = p.chromium.launch(headless=self.headless)
                browser_name = "Chromium"
            except Exception:
                pass

            if not browser:
                try:
                    browser = p.chromium.launch(headless=self.headless, channel="chrome")
                    browser_name = "Chrome"
                except Exception:
                    pass

            if not browser:
                try:
                    browser = p.firefox.launch(headless=self.headless)
                    browser_name = "Firefox"
                except Exception:
                    pass

            if not browser:
                logger.error("No browser available")
                return

            logger.info(f"Using browser: {browser_name}")

            # Create single context (session) for all tabs
            context = browser.new_context()

            # Step 1: Open first URL and login
            first_row = active_rows.iloc[0]
            logger.info(f"\n{'='*50}")
            logger.info("Step 1: Opening first URL and logging in...")

            first_page = context.new_page()
            first_page.goto(first_row['url'], wait_until="networkidle", timeout=30000)

            if self.is_login_page(first_page):
                logger.info("Login page detected, logging in...")
                if not self.login(first_page, first_row['userid'], first_row['password']):
                    logger.error("Login failed, aborting")
                    context.close()
                    browser.close()
                    return

                # Navigate back to first URL after login
                first_page.goto(first_row['url'], wait_until="domcontentloaded", timeout=30000)
                first_page.wait_for_load_state("networkidle", timeout=30000)

            logger.info("Login successful, session established")

            # Step 2: Open all other URLs in new tabs
            logger.info(f"\n{'='*50}")
            logger.info(f"Step 2: Opening {len(active_rows) - 1} additional tabs...")

            pages = [first_page]
            urls = [first_row['url']]

            for idx in range(1, len(active_rows)):
                row = active_rows.iloc[idx]
                logger.info(f"Opening tab {idx + 1}: {row['url']}")

                page = context.new_page()
                page.goto(row['url'], wait_until="domcontentloaded", timeout=30000)
                pages.append(page)
                urls.append(row['url'])

            # Wait for all tabs to load
            logger.info("Waiting for all tabs to load...")
            for page in pages:
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

            # Step 3: Process each tab - toggle, verify, record, close
            logger.info(f"\n{'='*50}")
            logger.info("Step 3: Processing each tab...")

            for idx, (page, url) in enumerate(zip(pages, urls)):
                logger.info(f"\n--- Tab {idx + 1}/{len(pages)}: {url.split('/')[-1]} ---")

                # Bring tab to front
                page.bring_to_front()
                page.wait_for_timeout(500)

                # Toggle and verify
                result = self.toggle_and_verify(page, url)
                result['userid'] = active_rows.iloc[idx]['userid']
                result['toggle'] = 'yes'

                self.results.append(result)

                logger.info(f"Result: {result['status']} - {result['message']}")

                # Close tab after processing
                page.close()
                logger.info(f"Tab closed")

            context.close()
            browser.close()

        self.save_results()
        self.print_summary()

    def save_results(self):
        """Save results to Excel (overwrites previous file)."""
        output_file = "toggle_results.xlsx"
        results_df = pd.DataFrame(self.results)
        results_df.to_excel(output_file, index=False)
        logger.info(f"Results saved to: {output_file}")

    def print_summary(self):
        """Print execution summary."""
        total = len(self.results)
        success = sum(1 for r in self.results if r['status'] == 'success')
        failed = sum(1 for r in self.results if r['status'] == 'failed')
        errors = sum(1 for r in self.results if r['status'] == 'error')

        logger.info("\n" + "="*50)
        logger.info("EXECUTION SUMMARY")
        logger.info("="*50)
        logger.info(f"Total processed: {total}")
        logger.info(f"Successful: {success}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Errors: {errors}")

        logger.info("\nDETAILED RESULTS:")
        for r in self.results:
            url_short = r['url'].split('/')[-1]
            logger.info(f"  {url_short}: {r['status']} | Before: {r['toggle_state_before']} | After: {r['toggle_state_after']}")


def main():
    parser = argparse.ArgumentParser(description='Automated Toggle Script')
    parser.add_argument('excel_file', help='Path to Excel file with URLs and credentials')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode (default: True)')
    parser.add_argument('--no-headless', action='store_false', dest='headless',
                        help='Run browser with visible window')

    args = parser.parse_args()

    if not Path(args.excel_file).exists():
        logger.error(f"Excel file not found: {args.excel_file}")
        return

    automation = ToggleAutomation(args.excel_file, args.headless)
    automation.run()


if __name__ == "__main__":
    main()
