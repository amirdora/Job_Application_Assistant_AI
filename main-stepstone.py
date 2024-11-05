# main-stepstone.py

import sys
import time
import click
import yaml
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from loguru import logger


def init_browser() -> webdriver.Chrome:
    """Initialize and return the Chrome WebDriver with required options, preserving session data."""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--user-data-dir=./chrome_user_data")
        options.add_argument("--window-size=1,1")  # Minimal size
        options.add_argument("--window-size=1920,1080")  # Set a window size for better compatibility
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.binary_location = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'  # Path for macOS

        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize browser: {str(e)}")


def load_resume_data(yaml_path: str) -> dict:
    """Load resume data from a YAML file."""
    with open(yaml_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)


def accept_cookies(browser):
    """Accept cookies on the Stepstone page if the prompt appears."""
    try:
        cookie_button = WebDriverWait(browser, 10).until(
            EC.element_to_be_clickable((By.ID, "ccmgt_explicit_accept"))
        )
        cookie_button.click()
        logger.info("Accepted cookies.")
    except WebDriverException:
        logger.warning("Cookie consent not found or already accepted.")


def is_logged_in(browser) -> bool:
    """Check if the user is already logged in by looking for a user-specific element."""
    try:
        WebDriverWait(browser, 3).until(
            EC.presence_of_element_located((By.XPATH, "//span[@data-genesis-element='TEXT' and text()='Amir']"))
        )
        logger.info("Already logged in, skipping login process.")
        return True
    except WebDriverException:
        logger.info("Not logged in, attempting login.")
        return False


def login(browser, retries=3):
    """Attempt to log in to the Stepstone account."""
    for attempt in range(retries):
        try:
            logger.info(f"Attempting login, try {attempt + 1} of {retries}")
            
            # Click the main Sign in menu to open the dropdown
            login_menu_button = WebDriverWait(browser, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='menu-item-sign-in-menu']"))
            )
            browser.execute_script("arguments[0].click();", login_menu_button)
            time.sleep(1)  # Small delay to ensure dropdown appears

            # Attempt to close any overlay that might appear
            close_overlay_if_exists(browser)
            
            # Wait for the dropdown and specifically click the "Sign in" option within it
            sign_in_option = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='sign-in']"))
            )
            browser.execute_script("arguments[0].click();", sign_in_option)  # Use JavaScript to ensure click
            logger.info("Clicked 'Sign in' from the dropdown.")

            perform_login(browser)  # Proceed with filling login details and submitting
            return True
        except WebDriverException as e:
            logger.error(f"Login attempt {attempt + 1} failed: {e}")
            time.sleep(2)  # Small delay before retry if an error occurs

    logger.error("Failed to log in after multiple attempts.")
    return False


def close_overlay_if_exists(browser):
    """Close any overlay dialog that may interfere with login."""
    try:
        overlay_dialog = WebDriverWait(browser, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".lpca-login-registration-components-1djedqi"))
        )
        close_button = overlay_dialog.find_element(By.CSS_SELECTOR, "button.close")
        close_button.click()
        logger.info("Closed overlay dialog.")
    except WebDriverException:
        logger.info("No overlay dialog to close.")


def load_config(config_path: str) -> dict:
    """Load configuration data from a YAML file."""
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def perform_login(browser):
    """Fill in login credentials from config file and submit the login form."""
    secrets = load_config('./data_folder/secrets.yaml')
    email = secrets.get("stepstone_username")
    password = secrets.get("stepstone_password")

    # Ensure both email and password are present in the config file
    if not email or not password:
        logger.error("Email or password is missing in the config file.")
        return

    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='email-input']"))
    ).send_keys(email)
    
    browser.find_element(By.CSS_SELECTOR, "[data-testid='password-input']").send_keys(password)
    browser.find_element(By.CSS_SELECTOR, "[data-testid='login-submit-btn']").click()
    
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.XPATH, "//span[@data-genesis-element='TEXT' and text()='Amir']"))
    )
    
    logger.info("Login successful, user profile detected.")

def find_job_listings_with_easy_apply(browser):
    """Locate job listings with 'Easy Apply' badge on the Stepstone page."""
    try:
        # Find all job listings
        job_listings = WebDriverWait(browser, 20).until(
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


def apply_to_job(browser, listing, field_mapping):
    """Apply to a job listing and handle form filling if necessary."""
    try:
        ActionChains(browser).move_to_element(listing).click(listing).perform()
        browser.switch_to.window(browser.window_handles[-1])

        apply_button = WebDriverWait(browser, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='harmonised-apply-button']"))
        )

        # Check if the button text indicates the job was already applied
        button_text = apply_button.text.strip()
        if button_text.lower() == "already applied":
            logger.info("Job already applied to, skipping.")
            browser.close()
            browser.switch_to.window(browser.window_handles[0])
        else:
            apply_button.click()
            logger.info("Clicked the apply button.")

        if check_redirect_to_external(browser):
            return  # Skip to the next job if redirected

        try:
            send_application_button = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='sendApplication']"))
            )
            send_application_button.click()
            logger.info("Clicked the send application button.")
            time.sleep(2)
            fill_form_with_yaml_data(browser, field_mapping)

        except WebDriverException:
            logger.info("'sendApplication' button not found. Proceeding with form filling if available.")
            fill_form_with_yaml_data(browser, field_mapping)

        if check_for_errors(browser):
            logger.warning("Form has errors. Pausing submission for this application.")
        elif check_submission_success(browser):
            logger.info("Application submitted successfully.")
            browser.close()
            browser.switch_to.window(browser.window_handles[0])
        else:
            logger.info("Application submission failed or incomplete.")
            browser.close()
            browser.switch_to.window(browser.window_handles[0])

    except WebDriverException as e:
        logger.error(f"Error while processing job listing: {e}")
        browser.close()
        browser.switch_to.window(browser.window_handles[0])


def check_redirect_to_external(browser) -> bool:
    """Check if the current tab redirected to an external site, close it if true."""
    time.sleep(2)
    if "stepstone.de" not in browser.current_url:
        logger.warning(f"Redirected to external site: {browser.current_url}. Closing tab and skipping.")
        browser.close()
        browser.switch_to.window(browser.window_handles[0])
        return True
    return False


def check_for_errors(browser) -> bool:
    """Check if there are any visible error messages on the form."""
    error_elements = browser.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'invalid-feedback')]")
    if error_elements:
        logger.warning("Form errors detected.")
        return True
    return False


def check_submission_success(browser) -> bool:
    """Check if the submission was successful by looking for a success message."""
    try:
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Your application has been sent – well done!')]"))
        )
        return True
    except WebDriverException:
        return False


def create_field_mapping(resume_data):
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


from selenium.common.exceptions import WebDriverException

def fill_form_with_yaml_data(browser, field_mapping):
    """Fill out only required fields in the form based on provided field mapping and dropdown questions."""

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
            dropdown = WebDriverWait(browser, 10).until(
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
    required_fields = browser.find_elements(By.XPATH, "//label[contains(@class, 'required')]")

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
    if check_for_errors(browser):
        logger.warning("Form has errors. Pausing submission for this application.")
        return  # Exit function if errors are detected

    # Submit the form if no errors are present
    try:
        submit_button = WebDriverWait(browser, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'].apply-button"))
        )
        submit_button.click()
        logger.info("Clicked submit button.")
    except WebDriverException:
        logger.warning("Submit button not found or clickable.")


def apply_for_jobs_on_stepstone(browser, yaml_path: str):
    """Search and apply for jobs on Stepstone with specified parameters."""
    resume_data = load_resume_data(yaml_path)
    field_mapping = create_field_mapping(resume_data)
    config = load_config("./data_folder/config.yaml")

    logger.info("Opening Stepstone job search page.")
    #browser.get("https://www.stepstone.de/work/fullstackentwickler-in/in-germany?radius=30&action=facet_selected%3bworkFromHome%3b1&q=Fullstackentwickler%2fin&ag=age_1&wfh=1")
    browser.get("https://www.stepstone.de/work/front-end-developer/in-frankfurt-am-main?action=facet_selected%3bage%3bage_1&ag=age_1")
    #browser.get("https://www.stepstone.de/work/in-germany?radius=30&action=facet_selected%3bsectors%3b21000&se=21000&wfh=1")

    accept_cookies(browser)

    if not is_logged_in(browser) and not login(browser):
        return

    job_listings = find_job_listings_with_easy_apply(browser)
    for listing in job_listings:
        try:
            # Get the job title to check if it should be skipped
            job_title = listing.find_element(By.CLASS_NAME, "res-nehv70").text
            if is_title_blacklisted(job_title, config):
                continue  # Skip applying for blacklisted job titles

            apply_to_job(browser, listing, field_mapping)
        except WebDriverException as e:
            logger.error(f"Error while processing job listing: {e}")
            continue

def is_title_blacklisted(job_title: str, config: dict) -> bool:
    """
    Check if the job title is blacklisted.
    
    Parameters:
    - job_title: The title of the job to check.
    - config: The configuration dictionary with blacklist terms.

    Returns:
    - True if the title is blacklisted, False otherwise.
    """
    title_blacklist = config.get("title_blacklist", [])
    job_title_lower = job_title.lower()

    for blacklisted_word in title_blacklist:
        if blacklisted_word.lower() in job_title_lower:
            logger.info(f"Skipping job '{job_title}' due to blacklisted term '{blacklisted_word}'.")
            return True
    return False

@click.command()
def main():
    """Main function to initialize and run the job application bot on Stepstone."""
    try:
        browser = init_browser()
        apply_for_jobs_on_stepstone(browser, "./data_folder/plain_text_resume.yaml")
    except WebDriverException as e:
        logger.error(f"WebDriver error occurred: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    main()
