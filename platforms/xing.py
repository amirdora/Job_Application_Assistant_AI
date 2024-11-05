# platforms/xing.py

from .base import JobPlatform
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)
import time
from datetime import datetime
from loguru import logger

class XingPlatform(JobPlatform):
    platform_name = "xing"  
    base_url = "https://www.xing.com"

    def login(self):
        """Manual login through a non-headless browser and save cookies."""
        self.browser = self.start_browser(headless=False)  # Initialize browser
        self.browser.get("https://login.xing.com/")
        print("Please log in to Xing in the opened browser window.")

        try:
            # Wait for the logged-in indicator
            WebDriverWait(self.browser, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-qa="frame-vnav-my-jobs"]'))
            )
            self.save_cookies()
            logger.info("User successfully logged in, and cookies have been saved.")
            return True
        except WebDriverException:
            logger.error("Login was not completed successfully within the time limit.")
            return False

    def construct_search_url(self):
        """Construct Xing job search URL based on user preferences."""
        preferences = self.config["job_preferences"]
        base_url = "https://www.xing.com/jobs/search?sc_o=jobs_search_button"

        keywords = preferences.get("job_title", "").replace(" ", "%20")
        location = preferences.get("location", "")
        radius = str(preferences.get("radius", 20))
        remote_option = '*'.join(preferences.get("remote_option", []))
        employment_type = '*'.join(preferences.get("employment_type", []))
        career_level = '*'.join(preferences.get("career_level", []))

        url = f"{base_url}&keywords={keywords}&location={location}&radius={radius}&sort=date"
        if remote_option:
            url += f"&remoteOption={remote_option}"
        if employment_type:
            url += f"&employmentType={employment_type}"
        if career_level:
            url += f"&careerLevel={career_level}"

        logger.info(f"Constructed Xing job search URL: {url}")
        return url

    def apply_jobs(self):
        """Start the headless job application process using saved cookies."""
        self.browser.get(self.construct_search_url())
        self.apply_for_jobs_on_xing()

    def apply_for_jobs_on_xing(self):
        """Iterate through job listings and apply if applicable."""
        try:
            job_listings = WebDriverWait(self.browser, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.results-styles__List-sc-31de7c67-0 li"))
            )
            logger.info(f"Found {len(job_listings)} job listings on Xing.")

            for listing in job_listings:
                try:
                    self.apply_to_job_in_new_tab(listing)
                    time.sleep(2)
                except WebDriverException as e:
                    logger.error(f"Error while processing job listing: {e}")

        except WebDriverException as e:
            logger.error(f"No job listings found or took too long to load on Xing: {e}")

    def apply_to_job_in_new_tab(self, listing):
        """Apply to a job listing on Xing in a new tab, ensuring robust tab handling."""
        try:
            link_element = listing.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-result']")
            listing_url = link_element.get_attribute("href")

            if not listing_url:
                logger.error("No URL found for job listing. Skipping this listing.")
                return

            self.browser.execute_script("window.open(arguments[0], '_blank');", listing_url)
            self.browser.switch_to.window(self.browser.window_handles[-1])

            if "xing.com" not in self.browser.current_url:
                logger.warning("Opened page is not on Xing. Closing tab and returning to listings.")
                self.browser.close()
                self.browser.switch_to.window(self.browser.window_handles[0])
                return

            if self.already_applied():
                logger.info("Job already applied to. Skipping to the next job listing.")
                self.browser.close()
                self.browser.switch_to.window(self.browser.window_handles[0])
                return

            if not self.click_easy_apply_and_send():
                logger.info("'Easy apply' button not available. Skipping to next listing.")
                self.browser.close()
                self.browser.switch_to.window(self.browser.window_handles[0])
                return

            if self.check_submission_success():
                self.applications.append({
                    "job_url": self.browser.current_url,
                    "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                logger.info("Application submitted successfully.")

        except WebDriverException as e:
            logger.error(f"Error while processing job listing: {e}")

        finally:
            if len(self.browser.window_handles) > 1:
                self.browser.close()
            self.browser.switch_to.window(self.browser.window_handles[0])

    def already_applied(self) -> bool:
        """Check if the job has already been applied to based on confirmation text."""
        try:
            WebDriverWait(self.browser, 4).until(
                EC.visibility_of_element_located((By.XPATH, "//div[contains(text(), 'You applied for this job')]"))
            )
            return True
        except WebDriverException:
            return False

    def click_easy_apply_and_send(self) -> bool:
        """Click 'Easy apply' and 'Send application' buttons if available."""
        try:
            # Step 1: Click 'Easy apply' button
            for attempt in range(3):
                try:
                    easy_apply_button = WebDriverWait(self.browser, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='apply-button']"))
                    )
                    if "Easy apply" in easy_apply_button.text:
                        easy_apply_button.click()
                        logger.info("Clicked 'Easy apply' button.")
                        break
                except (StaleElementReferenceException, ElementClickInterceptedException) as e:
                    logger.warning(f"Attempt {attempt + 1}: Failed to click 'Easy apply' due to {e}. Retrying...")
                except TimeoutException:
                    logger.warning("'Easy apply' button not available. Skipping to next listing.")
                    return False

            # Step 2: Click 'Send application' button
            self.click_send_application_button()
            return True

        except Exception as e:
            logger.error(f"Error clicking 'Easy apply' or 'Send application' button: {e}")
            return False

    def click_send_application_button(self):
        """Find and click the 'Send application' button with optimized handling."""
        try:
            send_button = WebDriverWait(self.browser, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Send application']]"))
            )
            send_button.click()
            time.sleep(5)  # Wait for the application to be submitted
            logger.info("Clicked 'Send application' button successfully.")
        except TimeoutException:
            logger.error("Timed out waiting for 'Send application' button.")
        except WebDriverException as e:
            logger.error(f"Error clicking 'Send application' button: {e}")
            # Try a JavaScript click as a fallback
            try:
                send_button_js = self.browser.find_element(By.XPATH, "//button[.//span[text()='Send application']]")
                self.browser.execute_script("arguments[0].click();", send_button_js)
                logger.info("Clicked 'Send application' button using JavaScript fallback.")
            except Exception as e_js:
                logger.error(f"Failed to click 'Send application' button with JavaScript fallback: {e_js}")

    def check_submission_success(self) -> bool:
        """Check if the submission was successful by looking for a success message."""
        try:
            WebDriverWait(self.browser, 4).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.success-styles__ImageContainer-sc-8138dec4-0"))
            )
            return True
        except WebDriverException:
            return False
