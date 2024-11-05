# platforms/stepstone.py

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


class StepStonePlatform(JobPlatform):
    platform_name = "stepstone"  # Define as class variable
    base_url = "https://www.stepstone.de/"

    def start_browser(self, headless=True):
        """Initialize and return the Chrome WebDriver with required options."""
        options = webdriver.ChromeOptions()
        if headless:
            options.headless = True
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--user-data-dir=./chrome_user_data_stepstone")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        # Adjust binary location if necessary
        # options.binary_location = '/path/to/chrome'

        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def login(self):
        """Login to StepStone using stored credentials."""
        if self.is_logged_in():
            return True  # Already logged in

        if not self.perform_login():
            logger.error("Failed to log in to StepStone.")
            return False

        self.save_cookies()
        return True

    def is_logged_in(self) -> bool:
        """Check if the user is already logged in."""
        try:
            self.browser.get(self.base_url)
            WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//span[@data-genesis-element='TEXT' and contains(text(), 'Amir')]")
                )
            )
            logger.info("Already logged in to StepStone.")
            return True
        except WebDriverException:
            logger.info("Not logged in to StepStone.")
            return False

    def perform_login(self):
        """Perform the login process using credentials from the config file."""
        try:
            logger.info("Attempting to log in to StepStone.")

            self.browser.get(self.base_url)

            # Click the main Sign in menu to open the dropdown
            login_menu_button = WebDriverWait(self.browser, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='menu-item-sign-in-menu']"))
            )
            self.browser.execute_script("arguments[0].click();", login_menu_button)
            time.sleep(1)  # Small delay to ensure dropdown appears

            # Close any overlay that might appear
            self.close_overlay_if_exists()

            # Click the "Sign in" option within the dropdown
            sign_in_option = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='sign-in']"))
            )
            self.browser.execute_script("arguments[0].click();", sign_in_option)
            logger.info("Clicked 'Sign in' from the dropdown.")

            # Fill in login credentials
            self.fill_login_credentials()
            return True
        except WebDriverException as e:
            logger.error(f"Login failed: {e}")
            return False

    def close_overlay_if_exists(self):
        """Close any overlay dialog that may interfere with login."""
        try:
            overlay_dialog = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".lpca-login-registration-components-1djedqi"))
            )
            close_button = overlay_dialog.find_element(By.CSS_SELECTOR, "button.close")
            close_button.click()
            logger.info("Closed overlay dialog.")
        except WebDriverException:
            logger.info("No overlay dialog to close.")

    def fill_login_credentials(self):
        """Fill in login credentials and submit."""
        secrets = self.load_config('./data_folder/secrets.yaml')
        email = secrets.get("stepstone_username")
        password = secrets.get("stepstone_password")

        if not email or not password:
            logger.error("Email or password is missing in the secrets.yaml file.")
            return False

        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='email-input']"))
        ).send_keys(email)

        self.browser.find_element(By.CSS_SELECTOR, "[data-testid='password-input']").send_keys(password)
        self.browser.find_element(By.CSS_SELECTOR, "[data-testid='login-submit-btn']").click()

        # Wait for the user profile element to confirm login
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//span[@data-genesis-element='TEXT' and contains(text(), 'Amir')]")
            )
        )
        logger.info("Login successful.")
        return True

    def construct_search_url(self):
        """Construct StepStone job search URL based on user preferences."""
        preferences = self.config["job_preferences"]
        base_url = "https://www.stepstone.de/jobs"

        keywords = preferences.get("job_title", "").replace(" ", "-")
        location = preferences.get("location", "").replace(" ", "-")
        radius = preferences.get("radius", 30)  # Default radius if not specified
        wfh = preferences.get("stepstone_wfh", "0")

        # Construct the search URL based on preferences
        url = f"{base_url}/{keywords}/in-{location}?radius={radius}"

        if wfh == "1":
            url += "&wfh=1"

        # Additional parameters can be added as needed

        logger.info(f"Constructed StepStone job search URL: {url}")
        return url

    def apply_jobs(self):
        """Start the job application process on StepStone."""
        self.browser.get(self.construct_search_url())
        self.accept_cookies()

        if not self.is_logged_in():
            if not self.login():
                return

        self.apply_for_jobs_on_stepstone()

    def accept_cookies(self):
        """Accept cookies on the StepStone page if the prompt appears."""
        try:
            cookie_button = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.ID, "ccmgt_explicit_accept"))
            )
            cookie_button.click()
            logger.info("Accepted cookies.")
        except WebDriverException:
            logger.warning("Cookie consent not found or already accepted.")

    def apply_for_jobs_on_stepstone(self):
        """Search and apply for jobs on StepStone."""
        resume_data = self.load_resume_data("./data_folder/plain_text_resume.yaml")
        field_mapping = self.create_field_mapping(resume_data)
        config = self.load_config("./data_folder/config.yaml")

        job_listings = self.find_job_listings_with_easy_apply()
        for listing in job_listings:
            try:
                # Get the job title to check if it should be skipped
                job_title = listing.find_element(By.CLASS_NAME, "res-nehv70").text
                if self.is_title_blacklisted(job_title, config):
                    continue  # Skip applying for blacklisted job titles

                self.apply_to_job(listing, field_mapping)
            except WebDriverException as e:
                logger.error(f"Error while processing job listing: {e}")
                continue

    def find_job_listings_with_easy_apply(self):
        """Locate job listings with 'Easy Apply' badge on the StepStone page."""
        try:
            # Find all job listings
            job_listings = WebDriverWait(self.browser, 20).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "res-1p8f8en"))
            )

            # Filter listings with "Easy Apply" badge
            easy_apply_listings = [
                listing for listing in job_listings
                if listing.find_elements(By.XPATH, ".//span[contains(text(), 'Easy Apply')]")
            ]

            logger.info(f"Found {len(easy_apply_listings)} 'Easy Apply' job listings to apply to.")
            return easy_apply_listings
        except WebDriverException:
            logger.error("No job listings with 'Easy Apply' found or took too long to load.")
            return []

    def apply_to_job(self, listing, field_mapping):
        """Apply to a job listing and handle form filling if necessary."""
        try:
            ActionChains(self.browser).move_to_element(listing).click(listing).perform()
            self.browser.switch_to.window(self.browser.window_handles[-1])

            apply_button = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='harmonised-apply-button']"))
            )

            # Check if the button text indicates the job was already applied
            button_text = apply_button.text.strip()
            if button_text.lower() == "already applied":
                logger.info("Job already applied to, skipping.")
                self.browser.close()
                self.browser.switch_to.window(self.browser.window_handles[0])
                return
            else:
                apply_button.click()
                logger.info("Clicked the apply button.")

            if self.check_redirect_to_external():
                return  # Skip to the next job if redirected

            try:
                send_application_button = WebDriverWait(self.browser, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='sendApplication']"))
                )
                send_application_button.click()
                logger.info("Clicked the send application button.")
                time.sleep(2)
                self.fill_form_with_yaml_data(field_mapping)
            except WebDriverException:
                logger.info("'sendApplication' button not found. Proceeding with form filling if available.")
                self.fill_form_with_yaml_data(field_mapping)

            if self.check_for_errors():
                logger.warning("Form has errors. Pausing submission for this application.")
            elif self.check_submission_success():
                logger.info("Application submitted successfully.")
                self.applications.append({
                    "platform": self.platform_name,
                    "job_url": self.browser.current_url,
                    "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                self.browser.close()
                self.browser.switch_to.window(self.browser.window_handles[0])
            else:
                logger.info("Application submission failed or incomplete.")
                self.browser.close()
                self.browser.switch_to.window(self.browser.window_handles[0])

        except WebDriverException as e:
            logger.error(f"Error while processing job listing: {e}")
            self.browser.close()
            self.browser.switch_to.window(self.browser.window_handles[0])

    def check_redirect_to_external(self) -> bool:
        """Check if the current tab redirected to an external site, close it if true."""
        time.sleep(2)
        if "stepstone.de" not in self.browser.current_url:
            logger.warning(f"Redirected to external site: {self.browser.current_url}. Closing tab and skipping.")
            self.browser.close()
            self.browser.switch_to.window(self.browser.window_handles[0])
            return True
        return False

    def check_for_errors(self) -> bool:
        """Check if there are any visible error messages on the form."""
        error_elements = self.browser.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'invalid-feedback')]")
        if error_elements:
            logger.warning("Form errors detected.")
            return True
        return False

    def check_submission_success(self) -> bool:
        """Check if the submission was successful by looking for a success message."""
        try:
            WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Your application has been sent')]"))
            )
            return True
        except WebDriverException:
            return False

    def fill_form_with_yaml_data(self, field_mapping):
        """Fill out required fields in the form based on provided field mapping and dropdown questions."""
        # Predefined dropdown selections for specific questions
        dropdown_questions = {
            "Deutschkenntnisse": "B1",
            "Wohnst du in Deutschland und verfügst du über eine gültige Arbeitserlaubnis?": "Ja",
            "Sprichst du verhandlungssicheres Business-Englisch?": "Ja",
            "Besitzt du mehr als 3 Jahre Berufserfahrung im Frontend Engineering?": "Ja",
        }

        # Fill dropdown questions based on predefined mapping
        for question, answer in dropdown_questions.items():
            try:
                # Locate dropdown by question text
                dropdown = WebDriverWait(self.browser, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, f"//label[contains(text(), '{question}')]/following::select[1]")
                    )
                )
                # Select the option within the dropdown based on answer text
                option = dropdown.find_element(By.XPATH, f".//option[contains(text(), '{answer}')]")
                option.click()
                logger.info(f"Selected '{answer}' for question '{question}'")
            except WebDriverException:
                logger.warning(f"Could not select answer for '{question}'")

        # Fill required text input fields based on field_mapping
        required_fields = self.browser.find_elements(By.XPATH, "//label[contains(@class, 'required')]")

        for label in required_fields:
            label_text = label.text.strip()
            input_value = field_mapping.get(label_text, None)

            # Only proceed with text inputs, as dropdowns are handled in dropdown_questions
            if input_value:
                try:
                    input_field = label.find_element(By.XPATH, "following::input[1]")
                    input_field.clear()
                    input_field.send_keys(input_value)
                    logger.info(f"Filled required field '{label_text}' with '{input_value}'")
                except WebDriverException:
                    logger.warning(f"Could not find input for '{label_text}'")

        # Check for form errors before submitting
        if self.check_for_errors():
            logger.warning("Form has errors. Pausing submission for this application.")
            return  # Exit function if errors are detected

        # Submit the form if no errors are present
        try:
            submit_button = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'].apply-button"))
            )
            submit_button.click()
            logger.info("Clicked submit button.")
        except WebDriverException:
            logger.warning("Submit button not found or clickable.")

    def create_field_mapping(self, resume_data):
        """Map YAML data to expected form field labels."""
        personal_info = resume_data.get('personal_information', {})
        salary_expectations = resume_data.get('salary_expectations', {})
        availability = resume_data.get('availability', {})

        return {
            "Verfügbar ab": "01.01.2025",
            "Gehaltsvorstellung": salary_expectations.get("salary_range_usd", "50000 - 60000"),
            "Ort": personal_info.get("city", "Aschaffenburg"),
            "Vorname": personal_info.get("name", ""),
            "Nachname": personal_info.get("surname", ""),
            "Geburtsdatum": personal_info.get("date_of_birth", ""),
            "Nationalität": personal_info.get("country", ""),
            "E-Mail": personal_info.get("email", ""),
            "Mobil": personal_info.get("phone_prefix", "") + personal_info.get("phone", ""),
            "Straße": personal_info.get("address", "").split(",")[0].strip(),
            "PLZ": personal_info.get("zip_code", ""),
            "Frühester Eintritt": availability.get("notice_period", ""),
            "Gehaltsrange pro Jahr (brutto) von": salary_expectations.get("salary_range_usd", "").split("-")[0].strip(),
            "Gehaltsrange pro Jahr (brutto) bis": salary_expectations.get("salary_range_usd", "").split("-")[-1].strip(),
            "linkedin": personal_info.get("linkedin", ""),
            "github": personal_info.get("github", ""),
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
