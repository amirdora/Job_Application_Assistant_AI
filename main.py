import os
import yaml
from flask import Flask, render_template, redirect, url_for, request, flash
from platforms.stepstone import StepStonePlatform
from platforms.xing import XingPlatform
from loguru import logger

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Required for flashing messages

# Load configuration
def load_config():
    """Load configuration from the config.yaml file."""
    with open("user_data/config.yaml", "r") as file:
        return yaml.safe_load(file)

config = load_config()
logger.add(config["logging"]["log_file"], rotation="1 MB")

# Global variables
applications = []
automation_running = False  # Track if automation is running

@app.route("/")
def home():
    """Home page: Show login status, preferences, and automation options."""
    platforms = ['xing', 'stepstone']
    logged_in = {}
    for platform in platforms:
        cookies_file = f"cookies/{platform}.pkl"
        logged_in[platform] = os.path.exists(cookies_file)

    preferences = config.get("job_preferences", {})
    return render_template(
        "index.html",
        applications=applications,
        logged_in=logged_in,
        preferences=preferences,
        platforms=platforms,
        automation_running=automation_running
    )

@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    """Page to set or update job preferences."""
    if request.method == "POST":
        # Save preferences to config
        config["job_preferences"]["job_title"] = request.form.get("job_title")
        config["job_preferences"]["location"] = request.form.get("location")
        config["job_preferences"]["radius"] = int(request.form.get("radius"))

        config["job_preferences"]["xing_remote_option"] = request.form.getlist("xing_remote_option")
        config["job_preferences"]["xing_employment_type"] = request.form.getlist("xing_employment_type")
        config["job_preferences"]["xing_career_level"] = request.form.getlist("xing_career_level")

        config["job_preferences"]["stepstone_wfh"] = request.form.get("stepstone_wfh", "0")

        with open("user_data/config.yaml", "w") as file:
            yaml.safe_dump(config, file)

        flash("Preferences saved successfully!", "success")
        return redirect(url_for("home"))

    # Render preferences form
    preferences = config.get("job_preferences", {})
    return render_template("preferences.html", preferences=preferences)

@app.route("/login_platform")
def login_platform():
    """Page to choose a platform for login."""
    platforms = ['xing', 'stepstone']
    return render_template("login_platform.html", platforms=platforms)

@app.route("/login/<platform>")
def login(platform):
    """Login route for the specified platform."""
    if platform == 'xing':
        platform_instance = XingPlatform(config)
    elif platform == 'stepstone':
        platform_instance = StepStonePlatform(config)
    else:
        return "Platform not supported.", 400

    try:
        # Start the browser before performing any actions
        platform_instance.start_browser(headless=False)
        success = platform_instance.login()
        if success:
            flash(f"Logged in successfully to {platform.capitalize()}!", "success")
            return redirect(url_for("home"))
        else:
            flash(f"Login failed for {platform.capitalize()}. Please try again.", "error")
            return redirect(url_for("login_platform"))
    except Exception as e:
        logger.error(f"Error during login: {e}")
        flash("An error occurred during login. Please try again.", "error")
        return redirect(url_for("login_platform"))
    finally:
        platform_instance.quit_browser()  # Ensure the browser is closed

@app.route("/start_automation")
def start_automation():
    """Start the automation process."""
    global automation_running

    # Check if the user is logged in to any platform
    platforms = ['xing', 'stepstone']
    logged_in = any(os.path.exists(f"cookies/{platform}.pkl") for platform in platforms)

    if not logged_in:
        flash("Please log in to a platform to start automation.", "warning")
        return redirect(url_for("home"))

    if not automation_running:
        automation_running = True
        flash("Automation started!", "success")
    else:
        flash("Automation is already running!", "warning")
    return redirect(url_for("home"))

@app.route("/stop_automation")
def stop_automation():
    """Stop the automation process."""
    global automation_running
    if automation_running:
        automation_running = False
        flash("Automation stopped!", "success")
    else:
        flash("No automation process is running!", "warning")
    return redirect(url_for("home"))

if __name__ == "__main__":
    # Ensure required directories exist
    os.makedirs("cookies", exist_ok=True)
    os.makedirs("user_data", exist_ok=True)

    # Run the app
    app.run(debug=True, host="0.0.0.0", port=5001)