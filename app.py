# app.py

import os
import yaml
from flask import Flask, render_template, redirect, url_for, request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from platforms.stepstone import StepStonePlatform
from platforms.xing import XingPlatform
from loguru import logger

app = Flask(__name__)

def load_config():
    """Load configuration from the config.yaml file."""
    with open("user_data/config.yaml", "r") as file:
        return yaml.safe_load(file)

config = load_config()
logger.add(config["logging"]["log_file"], rotation="1 MB")

applications = []

@app.route("/login/<platform>")
def login(platform):
    """Login route for the specified platform."""
    # Initialize platform instance based on the platform string
    if platform == 'xing':
        platform_instance = XingPlatform(config)
    elif platform == 'stepstone':
        platform_instance = StepStonePlatform(config)
    else:
        return "Platform not supported.", 400

    # Now call start_browser through the platform instance
    platform_instance.browser = platform_instance.start_browser(headless=False)
    success = platform_instance.login()
    platform_instance.browser.quit()
    if success:
        return redirect(url_for("home"))
    else:
        return f"Login Failed for {platform.capitalize()}. Please try again."

@app.route("/apply_jobs/<platform>")
def apply_jobs(platform):
    """Start the job application process for the specified platform."""
    # Initialize platform instance based on the platform string
    if platform == 'xing':
        platform_instance = XingPlatform(config)
    elif platform == 'stepstone':
        platform_instance = StepStonePlatform(config)
    else:
        return "Platform not supported.", 400

    # Now call start_browser through the platform instance
    platform_instance.browser = platform_instance.start_browser(headless=False)

    if not platform_instance.load_cookies():
        logger.error(f"Cookies not found for {platform}. Please log in first.")
        platform_instance.browser.quit()
        return redirect(url_for("login", platform=platform))

    platform_instance.apply_jobs()
    applications.extend(platform_instance.applications)
    platform_instance.browser.quit()
    return redirect(url_for("home"))

@app.route("/")
def home():
    platforms = ['xing', 'stepstone']
    logged_in = {}
    for platform in platforms:
        cookies_file = f"cookies/{platform}.pkl"
        logged_in[platform] = os.path.exists(cookies_file)
    preferences = config.get("job_preferences", {})
    return render_template("index.html", applications=applications, logged_in=logged_in, preferences=preferences, platforms=platforms)

@app.route("/save_preferences", methods=["POST"])
def save_preferences():
    config["job_preferences"]["job_title"] = request.form.get("job_title")
    config["job_preferences"]["location"] = request.form.get("location")
    config["job_preferences"]["radius"] = int(request.form.get("radius"))

    config["job_preferences"]["xing_remote_option"] = request.form.getlist("xing_remote_option")
    config["job_preferences"]["xing_employment_type"] = request.form.getlist("xing_employment_type")
    config["job_preferences"]["xing_career_level"] = request.form.getlist("xing_career_level")

    config["job_preferences"]["stepstone_wfh"] = request.form.get("stepstone_wfh", "0")

    with open("user_data/config.yaml", "w") as file:
        yaml.safe_dump(config, file)
    return redirect(url_for("home"))

if __name__ == "__main__":
    import webbrowser
    webbrowser.open("http://127.0.0.1:5001")
    app.run(debug=True, host="0.0.0.0", port=5001)
