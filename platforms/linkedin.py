from utils.form_filler import FormFiller
from .base import JobPlatform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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
import yaml
from loguru import logger


class LinkedInPlatform(JobPlatform):

    platform_name = "linkedin"  # Define as class variable
    base_url = "https://www.linkedin.com/"

    def login(self):
        """Perform the login process using credentials from the config file."""
        try:
            logger.info("Attempting to log in to LinkedIn.")

            # Navigate to LinkedIn login page
            self.browser.get(f"{self.base_url}login")

            # Accept cookies if the prompt appears
            self.accept_cookies()

            # Fill in login credentials
            self.enter_credentials()

            # Save cookies after successful login
            self.save_cookies()
            return True
        except WebDriverException as e:
            logger.error(f"Login failed: {e}")
            return False

    def accept_cookies(self):
        """Accept cookies on the LinkedIn page if the prompt appears."""
        try:
            cookie_button = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[action-type='ACCEPT']"))
            )
            cookie_button.click()
            logger.info("Accepted cookies.")
        except WebDriverException:
            logger.warning("Cookie consent not found or already accepted.")

    def enter_credentials(self):
        try:
            logger.debug("Enter credentials...")
            
            check_interval = 4  # Interval to log the current URL
            elapsed_time = 0

            while True:
                # Log current URL every 4 seconds and remind the user to log in
                current_url = self.browser.current_url
                logger.info(f"Please login on {current_url}")

                # Check if the user is already on the feed page
                if 'feed' in current_url:
                    logger.debug("Login successful, redirected to feed page.")
                    break
                else:
                    # Optionally wait for the password field (or any other element you expect on the login page)
                    WebDriverWait(self.browser, 10).until(
                        EC.presence_of_element_located((By.ID, "password"))
                    )
                    logger.debug("Password field detected, waiting for login completion.")

                time.sleep(check_interval)
                elapsed_time += check_interval

        except TimeoutException:
            logger.error("Login form not found. Aborting login.")

    def construct_search_url(self):
        """Construct LinkedIn job search URL based on user preferences."""
        preferences = self.config["job_preferences"]
        base_url = f"{self.base_url}jobs/search/"

        keywords = preferences.get("job_title", "").replace(" ", "%20")
        location = preferences.get("location", "").replace(" ", "%20")
        remote = "&f_WT=2" if preferences.get("linkedin_remote", "0") == "1" else ""

        # Construct the search URL based on preferences
        url = f"{base_url}?keywords={keywords}&location={location}{remote}"
        logger.info(f"Constructed LinkedIn job search URL: {url}")
        return url

    def apply_jobs(self):
        """Start the job application process on LinkedIn."""
        self.browser = self.start_browser(headless=False)  # Initialize browser
        self.browser.get(self.base_url)
        if not self.login():
            logger.error("Login failed. Stopping automation.")
            return

        time.sleep(2)
        self.browser.get(self.construct_search_url())
        time.sleep(1)
        self.accept_cookies()

        try:
            self.apply_for_jobs_on_linkedin()
        except Exception as e:
            logger.error(f"Unexpected error during job application process: {e}")
        finally:
            self.browser.quit()
            logger.info("Browser closed after completing job applications.")

    def apply_for_jobs_on_linkedin(self):
        """Search and apply for jobs on LinkedIn."""
        resume_data = self.load_resume_data("./data_folder/plain_text_resume.yaml")
        field_mapping = self.create_field_mapping(resume_data)
        config = self.load_config("./data_folder/config.yaml")

        job_listings = self.find_job_listings()
        for listing in job_listings:
            try:
                # Get the job title to check if it should be skipped
                job_title = listing.find_element(By.CSS_SELECTOR, "h3.job-result-card__title").text
                if self.is_title_blacklisted(job_title, config):
                    continue  # Skip applying for blacklisted job titles

                self.apply_to_job(listing, field_mapping)
            except WebDriverException as e:
                logger.error(f"Error while processing job listing: {e}")
                continue

    def find_job_listings(self):
        """Locate job listings with 'Easy Apply' badge on LinkedIn."""
        try:
            # Wait for job listings to load
            # Find all <li> elements with the 'data-occludable-job-id' attribute
            job_elements = self.browser.find_elements(By.CSS_SELECTOR, 'li[data-occludable-job-id]')

            # Filter "Easy Apply" jobs
            easy_apply_jobs = []

            for job in job_elements:
                # Find all <span> elements within the job element
                spans = job.find_elements(By.CSS_SELECTOR, 'span')
                
                # Check if any <span> contains the text "Easy Apply"
                has_easy_apply = any(span.text == "Easy Apply" for span in spans)
                
                if has_easy_apply:
                    easy_apply_jobs.append(job)
                
            print(f"Found {len(easy_apply_jobs)} 'Easy Apply' jobs.")
            return easy_apply_jobs
        
        except Exception as e:
            print(f"Error extracting job details: {e}")

    def scroll_to_load_more_jobs(self):
        """Scroll to load more job listings if pagination exists."""
        try:
            scroll_pause_time = 2  # Time to wait between scrolls
            last_height = self.browser.execute_script("return document.body.scrollHeight")

            while True:
                # Scroll down to the bottom of the page
                self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(scroll_pause_time)

                # Calculate new scroll height and compare with last scroll height
                new_height = self.browser.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
        except WebDriverException as e:
            logger.error(f"Error while scrolling to load more jobs: {e}")

    def apply_to_job(self, listing, field_mapping):
        """Apply to a job listing and handle form filling if necessary."""
        try:
            # Click on the job listing
            listing.click()
            time.sleep(2)  # Wait for the job details to load

            # Click the "Easy Apply" button
            easy_apply_button = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.jobs-apply-button"))
            )
            easy_apply_button.click()
            time.sleep(2)  # Wait for the application form to load

            # Use FormFiller to fill and submit the form
            self.fill_form_using_llm()

            if self.check_submission_success():
                logger.info("Application submitted successfully.")
                self.applications.append({
                    "platform": self.platform_name,
                    "job_url": self.browser.current_url,
                    "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                logger.info("Application submission failed or incomplete.")

        except Exception as e:
            logger.error(f"Error while processing job listing: {e}")
        finally:
            # Close the current tab and continue with the next job
            time.sleep(1)  # Allow time for error handling or user intervention
            self.browser.close()
            self.browser.switch_to.window(self.browser.window_handles[0])

    def fill_form_using_llm(self):
        """Use OpenAI to fill out the form."""
        try:
            secrets = self.load_config('./data_folder/secrets.yaml')
            resume_data = self.load_config('./data_folder/plain_text_resume.yaml')
            openai_key = secrets.get("llm_api_key")

            form_filler = FormFiller(resume_data, openai_api_key=openai_key, driver=self.browser)
            form_filler.fill_and_submit_form()
        except Exception as e:
            logger.error(f"Error while filling form using OpenAI: {e}")

    def check_submission_success(self) -> bool:
        """Check if the submission was successful by looking for a success message."""
        try:
            WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.artdeco-toast-item--success"))
            )
            return True
        except WebDriverException:
            return False

    def create_field_mapping(self, resume_data):
        """Map YAML data to expected form field labels."""
        personal_info = resume_data.get('personal_information', {})
        salary_expectations = resume_data.get('salary_expectations', {})
        availability = resume_data.get('availability', {})

        return {
            "First Name": personal_info.get("name", ""),
            "Last Name": personal_info.get("surname", ""),
            "Email": personal_info.get("email", ""),
            "Phone": personal_info.get("phone_prefix", "") + personal_info.get("phone", ""),
            "Address": personal_info.get("address", ""),
            "City": personal_info.get("city", ""),
            "Postal Code": personal_info.get("zip_code", ""),
            "Country": personal_info.get("country", ""),
        }

    def is_title_blacklisted(self, job_title: str, config: dict) -> bool:
        """Check if the job title is blacklisted."""
        title_blacklist = config.get("title_blacklist", [])
        job_title_lower = job_title.lower()

        for blacklisted_word in title_blacklist:
            if blacklisted_word.lower() in job_title_lower:
                logger.info(f"Skipping job '{job_title}' due to blacklisted term '{blacklisted_word}'.")
                return True
        return False

    def load_resume_data(self, yaml_path: str) -> dict:
        """Load resume data from a YAML file."""
        with open(yaml_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def load_config(self, config_path: str) -> dict:
        """Load configuration data from a YAML file."""
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)