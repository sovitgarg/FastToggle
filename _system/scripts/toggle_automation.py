"""
Automated Toggle Script
Reads URLs from Excel and sets toggle to desired state (ON/OFF).
Uses single login session with multiple tabs for efficiency.

Excel format:
URL | userid | password
https://example.com/settings | user1 | pass1
https://example.com/settings | user2 | pass2

Usage:
python toggle_automation.py "ToggleExcel_A.xlsx" --state ON --no-headless
python toggle_automation.py "ToggleExcel_B.xlsx" --state OFF --no-headless
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
    def __init__(self, excel_path: str, state: str, headless: bool = True):
        self.excel_path = excel_path
        self.state = state.strip().upper()  # ON or OFF
        self.headless = headless
        self.results = []

        if self.state not in ['ON', 'OFF']:
            raise ValueError(f"Invalid state: {state}. Must be ON or OFF.")

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

    def set_toggle_state(self, page, url: str, desired_state: str) -> dict:
        """Set the toggle to desired state (ON/OFF) and verify the result."""
        result = {
            'url': url,
            'status': 'failed',
            'desired_state': desired_state.upper(),
            'toggle_state_before': 'UNKNOWN',
            'toggle_state_after': 'UNKNOWN',
            'message': '',
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Validate desired_state
        desired_state = desired_state.strip().lower()
        if desired_state not in ['on', 'off']:
            result['status'] = 'skipped'
            result['message'] = f'Invalid toggle value: {desired_state}. Expected ON or OFF.'
            return result

        desired_checked = (desired_state == 'on')

        try:
            # Wait for page to fully load
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                logger.info("Page still loading, continuing...")
            page.wait_for_timeout(3000)

            # Dismiss any Pendo popups that may be blocking
            self.dismiss_popups(page)

            # Check state before toggle
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
                result['message'] = 'Toggle element not found (timeout waiting for element after retry)'
                return result

            toggle = page.locator(toggle_selector).first

            if toggle.count() == 0:
                result['message'] = 'Toggle element not found'
                return result

            state_before = toggle.is_checked()
            result['toggle_state_before'] = 'ON' if state_before else 'OFF'
            logger.info(f"Toggle state before: {result['toggle_state_before']}, Desired: {desired_state.upper()}")

            # Check if already in desired state
            if state_before == desired_checked:
                result['status'] = 'success'
                result['toggle_state_after'] = result['toggle_state_before']
                result['message'] = f'Already in desired state: {desired_state.upper()}'
                logger.info(f"Already in desired state, no action needed")
                return result

            # Need to toggle - dismiss popups before clicking
            self.dismiss_popups(page)

            # Click toggle with force option to bypass any remaining overlays
            try:
                page.click(toggle_selector, timeout=5000)
            except Exception:
                logger.info("Normal click failed, trying force click...")
                page.locator(toggle_selector).first.click(force=True)
            logger.info("Toggle clicked")

            # Wait for UI update
            page.wait_for_timeout(500)

            # Dismiss popups before save
            self.dismiss_popups(page)

            # Click save
            save_selectors = [
                'button:has-text("Save Integration")',
                'button:has-text("Save")',
            ]

            saved = False
            for selector in save_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        try:
                            page.click(selector, timeout=5000)
                        except Exception:
                            page.locator(selector).first.click(force=True)
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

            # Determine success based on achieving desired state
            if state_after == desired_checked:
                result['status'] = 'success'
                result['message'] = f'Toggle set to {desired_state.upper()} (was {result["toggle_state_before"]})'
            else:
                result['status'] = 'failed'
                result['message'] = f'Failed to set toggle to {desired_state.upper()}. Current state: {result["toggle_state_after"]}'

        except Exception as e:
            result['status'] = 'error'
            result['message'] = str(e)
            logger.error(f"Error: {str(e)}")

        return result

    def run(self):
        """Main execution method using tabs."""
        df = self.load_excel()

        if len(df) == 0:
            logger.info("No rows found in Excel")
            return

        logger.info(f"Processing {len(df)} URLs - Setting all to {self.state}")

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
            first_row = df.iloc[0]
            logger.info(f"\n{'='*50}")
            logger.info("Step 1: Opening first URL and logging in...")

            first_page = context.new_page()
            first_page.goto(first_row['url'], wait_until="domcontentloaded", timeout=60000)
            try:
                first_page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                logger.info("Page still loading, continuing anyway...")

            if self.is_login_page(first_page):
                logger.info("Login page detected, logging in...")
                if not self.login(first_page, first_row['userid'], first_row['password']):
                    logger.error("Login failed, aborting")
                    context.close()
                    browser.close()
                    return

                # Navigate back to first URL after login
                first_page.goto(first_row['url'], wait_until="domcontentloaded", timeout=60000)
                try:
                    first_page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    logger.info("Page still loading, continuing anyway...")

            logger.info("Login successful, session established")

            # Step 2: Open all other URLs in new tabs
            logger.info(f"\n{'='*50}")
            logger.info(f"Step 2: Opening {len(df) - 1} additional tabs...")

            pages = [first_page]
            urls = [first_row['url']]

            for idx in range(1, len(df)):
                row = df.iloc[idx]
                logger.info(f"Opening tab {idx + 1}: {row['url']}")

                page = context.new_page()
                page.goto(row['url'], wait_until="domcontentloaded", timeout=60000)
                pages.append(page)
                urls.append(row['url'])

            # Wait for all tabs to load
            logger.info("Waiting for all tabs to load...")
            for page in pages:
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    logger.info("Tab still loading, continuing...")

            # Step 3: Process each tab - set toggle state, verify, record, close
            logger.info(f"\n{'='*50}")
            logger.info("Step 3: Processing each tab...")

            for idx, (page, url) in enumerate(zip(pages, urls)):
                logger.info(f"\n--- Tab {idx + 1}/{len(pages)}: {url.split('/')[-1]} (Set to: {self.state}) ---")

                # Bring tab to front
                page.bring_to_front()
                page.wait_for_timeout(500)

                # Set toggle to desired state and verify
                result = self.set_toggle_state(page, url, self.state)
                result['userid'] = df.iloc[idx]['userid']

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
        skipped = sum(1 for r in self.results if r['status'] == 'skipped')

        logger.info("\n" + "="*50)
        logger.info("EXECUTION SUMMARY")
        logger.info("="*50)
        logger.info(f"Total processed: {total}")
        logger.info(f"Successful: {success}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Errors: {errors}")
        logger.info(f"Skipped: {skipped}")

        logger.info("\nDETAILED RESULTS:")
        for r in self.results:
            url_short = r['url'].split('/')[-1]
            desired = r.get('desired_state', 'N/A')
            logger.info(f"  {url_short}: {r['status']} | Desired: {desired} | Before: {r['toggle_state_before']} | After: {r['toggle_state_after']}")


def main():
    parser = argparse.ArgumentParser(description='Automated Toggle Script')
    parser.add_argument('excel_file', help='Path to Excel file with URLs and credentials')
    parser.add_argument('--state', required=True, choices=['ON', 'OFF', 'on', 'off'],
                        help='Desired toggle state: ON or OFF')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode (default: True)')
    parser.add_argument('--no-headless', action='store_false', dest='headless',
                        help='Run browser with visible window')

    args = parser.parse_args()

    if not Path(args.excel_file).exists():
        logger.error(f"Excel file not found: {args.excel_file}")
        return

    automation = ToggleAutomation(args.excel_file, args.state, args.headless)
    automation.run()


if __name__ == "__main__":
    main()
