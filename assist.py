import os
import time
import yaml
import pickle
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from loguru import logger

app = Flask(__name__)

# Load configuration and set up logging
def load_config():
    """Load configuration from the config.yaml file."""
    with open("user_data/config.yaml", "r") as file:
        return yaml.safe_load(file)

config = load_config()
logger.add(config["logging"]["log_file"], rotation="1 MB")

# Store applications in a global list for demonstration
applications = []

def start_browser(headless=True):
    """Initialize the Chrome WebDriver with options."""
    options = webdriver.ChromeOptions()
    options.headless = headless
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def load_cookies(browser):
    """Load cookies from a saved file."""
    if os.path.exists("cookies.pkl"):
        browser.get("https://www.xing.com")
        with open("cookies.pkl", "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies:
                if "domain" in cookie:
                    del cookie["domain"]
                browser.add_cookie(cookie)
        return True
    return False

def save_cookies(browser):
    """Save cookies to a file for future sessions."""
    with open("cookies.pkl", "wb") as file:
        pickle.dump(browser.get_cookies(), file)

@app.route("/")
def home():
    """Render the home page with login option, application history, and job preferences."""
    logged_in = os.path.exists("cookies.pkl")
    preferences = config.get("job_preferences", {})
    return render_template("index.html", applications=applications, logged_in=logged_in, preferences=preferences)

@app.route("/login")
def login():
    """Manual login through a non-headless browser and save cookies."""
    browser = start_browser(headless=False)
    try:
        browser.get("https://login.xing.com/")
        print("Please log in to Xing in the opened browser window.")
        
        # Wait for the logged-in indicator
        try:
            WebDriverWait(browser, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-qa="frame-vnav-my-jobs"]'))
            )
        except WebDriverException:
            logger.error("Login was not completed successfully within the time limit.")
            browser.quit()
            return "Login Failed. Please try again."
        
        save_cookies(browser)
        logger.info("User successfully logged in, and cookies have been saved.")
        
        browser.quit()
        return redirect(url_for("home"))
    except WebDriverException as e:
        logger.error(f"Login failed: {e}")
        browser.quit()
        return "Login Failed. Please try again."

@app.route("/apply_jobs")
def apply_jobs():
    """Start the headless job application process using saved cookies."""
    browser = start_browser(headless=True)
    browser.get("https://www.xing.com")
    if not load_cookies(browser):
        logger.error("Cookies not found. Please log in first.")
        return redirect(url_for("login"))
    
    browser.refresh()
    job_search_url = construct_xing_url()
    logger.info(f"Job search URL constructed: {job_search_url}")

    browser.get(job_search_url)
    apply_for_jobs_on_xing(browser)
    browser.quit()
    
    return redirect(url_for("home"))

@app.route("/save_preferences", methods=["POST"])
def save_preferences():
    """Save updated job search preferences from the form to config.yaml."""
    config["job_preferences"]["job_title"] = request.form.get("job_title")
    config["job_preferences"]["location"] = request.form.get("location")
    config["job_preferences"]["radius"] = int(request.form.get("radius"))
    
    # Get multiple checkbox values as lists
    config["job_preferences"]["remote_option"] = request.form.getlist("remote_option")
    config["job_preferences"]["employment_type"] = request.form.getlist("employment_type")
    config["job_preferences"]["career_level"] = request.form.getlist("career_level")
    
    with open("user_data/config.yaml", "w") as file:
        yaml.safe_dump(config, file)
    return redirect(url_for("home"))

def construct_xing_url():
    """Construct Xing job search URL based on user preferences."""
    preferences = config["job_preferences"]
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

def apply_for_jobs_on_xing(browser):
    """Iterate through job listings and apply if applicable."""
    try:
        job_listings = WebDriverWait(browser, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.results-styles__List-sc-31de7c67-0 li"))
        )
        logger.info(f"Found {len(job_listings)} job listings on Xing.")

        for listing in job_listings:
            try:
                apply_to_job_in_new_tab(browser, listing)
                time.sleep(2)
            except WebDriverException as e:
                logger.error(f"Error while processing job listing: {e}")

    except WebDriverException as e:
        logger.error(f"No job listings found or took too long to load on Xing: {e}")

def apply_to_job_in_new_tab(browser, listing):
    """Apply to a job listing on Xing in a new tab, ensuring robust tab handling."""
    try:
        link_element = listing.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-result']")
        listing_url = link_element.get_attribute("href")

        if not listing_url:
            logger.error("No URL found for job listing. Skipping this listing.")
            return

        browser.execute_script("window.open(arguments[0], '_blank');", listing_url)
        browser.switch_to.window(browser.window_handles[-1])

        if "xing.com" not in browser.current_url:
            logger.warning("Opened page is not on Xing. Closing tab and returning to listings.")
            browser.close()
            browser.switch_to.window(browser.window_handles[0])
            return

        if already_applied(browser):
            logger.info("Job already applied to. Skipping to the next job listing.")
            browser.close()
            browser.switch_to.window(browser.window_handles[0])
            return

        if not click_easy_apply_and_send(browser):
            logger.info("'Easy apply' button not available. Skipping to next listing.")
            browser.close()
            browser.switch_to.window(browser.window_handles[0])
            return

        if check_submission_success(browser):
            applications.append({
                "job_url": browser.current_url,
                "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.info("Application submitted successfully.")

    except WebDriverException as e:
        logger.error(f"Error while processing job listing: {e}")

    finally:
        if len(browser.window_handles) > 1:
            browser.close()
        browser.switch_to.window(browser.window_handles[0])

def already_applied(browser) -> bool:
    """Check if the job has already been applied to based on confirmation text."""
    try:
        WebDriverWait(browser, 4).until(
            EC.visibility_of_element_located((By.XPATH, "//div[contains(text(), 'You applied for this job')]"))
        )
        return True
    except WebDriverException:
        return False

def click_easy_apply_and_send(browser):
    """Click 'Easy apply' and 'Send application' buttons if available."""
    try:
        # Step 1: Click 'Easy apply' button, with retries in case of interference or delays
        for attempt in range(3):
            try:
                easy_apply_button = WebDriverWait(browser, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='apply-button']"))
                )
                if "Easy apply" in easy_apply_button.text:
                    easy_apply_button.click()
                    logger.info("Clicked 'Easy apply' button.")
                    break
            except (StaleElementReferenceException, ElementClickInterceptedException) as e: # type: ignore
                logger.warning(f"Attempt {attempt + 1}: Failed to click 'Easy apply' due to {e}. Retrying...")
            except TimeoutException:
                logger.warning("'Easy apply' button not available. Skipping to next listing.")
                return

        # Step 2: Click 'Send application' button with similar retries
        click_send_application_button(browser)

    except Exception as e:
        logger.error(f"Error clicking 'Easy apply' or 'Send application' button: {e}")


def click_send_application_button(browser):
    """Find and click the 'Send application' button with optimized handling."""
    try:
        # Wait for the 'Send application' button to be present and clickable
        send_button = WebDriverWait(browser, 15).until(
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
            send_button_js = browser.find_element(By.XPATH, "//button[.//span[text()='Send application']]")
            browser.execute_script("arguments[0].click();", send_button_js)
            logger.info("Clicked 'Send application' button using JavaScript fallback.")
        except Exception as e_js:
            logger.error(f"Failed to click 'Send application' button with JavaScript fallback: {e_js}")


def check_submission_success(browser) -> bool:
    """Check if the submission was successful by looking for a success message."""
    try:
        WebDriverWait(browser, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.success-styles__ImageContainer-sc-8138dec4-0"))
        )
        return True
    except WebDriverException:
        return False

if __name__ == "__main__":
    import webbrowser
    webbrowser.open("http://127.0.0.1:5001")
    app.run(debug=True, host="0.0.0.0", port=5001)
