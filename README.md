
# Xing Job Application AI Applier

The **Xing Job Application AI Applier** automates job applications on the Xing platform based on user-defined preferences. This AI Applier allows users to log in manually (without sharing credentials), specify job types, locations, and remote/onsite preferences in a configuration file, and captures session cookies to perform headless applications.

![alt text](/Readme/screenshot.png)

## Disclaimer

**This AI Applier is intended for personal use only.** Automating job applications on Xing or any other platform may violate the terms of service of those platforms. **Use this AI Applier at your own risk.** The developers of this AI Applier assume no responsibility for any actions taken with it, and users are solely responsible for compliance with Xing’s terms of use and all applicable laws.


## Features

- **Manual Login**: Users log in manually without sharing credentials.
- **Headless Automation**: The AI Applier uses headless mode to apply for jobs automatically based on user preferences.
- **Configurable Preferences**: Job search preferences are stored in a configuration file (`config.yaml`).
- **Logging**: All application processes and outcomes are logged for easy reference.

---

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [For Windows](#windows-installation)
  - [For macOS](#macos-installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

1. **Python 3.8+**: Ensure Python is installed on your system.
   - Verify by running `python --version` or `python3 --version` in your command line.
2. **Pip**: Pip should be installed with Python. Verify by running `pip --version`.
3. **Chrome Browser**: The AI Applier uses Chrome for automation. [Download Chrome](https://www.google.com/chrome/) if it's not installed.

## Installation

### Windows Installation

1. **Clone the Repository**: 
   ```bash
   git clone https://github.com/amirdora/Auto_Jobs_Applier_AI.git
   cd xing-job-application-AI Applier
   ```
2. **Create and Activate a Virtual Environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
3. **Install Requirements in the Virtual Environment**:
   ```bash
   pip install -r requirements.txt
   ```

### macOS Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/xing-job-application-AI Applier.git
   cd xing-job-application-AI Applier
   ```
2. **Create and Activate a Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install Requirements in the Virtual Environment**:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. **Create a `config.yaml` File**: Set up job preferences in `config.yaml` to specify job type, location, remote preference, and logging file path.

Example `config.yaml`:
   ```yaml
   # config.yaml

   job_preferences:
     job_type: "Developer"         # Job title to search for
     location: "Frankfurt"         # Job location
     remote: "yes"                 # Options: "yes" for remote, "no" for on-site
     city_id: "2925533.36f095"     # City ID for Frankfurt, change based on target location

   logging:
     log_file: "application_log.txt"   # Path for log file
   ```
   Update `job_type`, `location`, `remote`, and `city_id` to match your preferences. The `log_file` specifies where application logs are stored.

## Usage

1. **Run the AI Applier**:

   With the virtual environment activated, run the main script:
   ```bash
   python AI Applier.py
   ```

2. **Login**:

   A window will prompt you to log in to Xing manually. Use the Chrome browser window to complete the login.
   Close the prompt once logged in; the AI Applier will capture cookies and proceed with the headless application process.

3. **Monitor Logs**:

   All actions are logged in `application_log.txt`. Open this file to track which jobs have been applied to, along with timestamps and any errors encountered.

## Troubleshooting

### Common Issues

- **ChromeDriver Compatibility**:

  If you encounter ChromeDriver issues, make sure that AI Applierh Chrome and ChromeDriver are updated. If issues persist, specify the ChromeDriver version in `requirements.txt` and reinstall:
  ```bash
  pip install -r requirements.txt
  ```

- **Login Issues**:

  Ensure that you complete the login manually. The AI Applier waits for the login process but will timeout if login takes too long. Restart the script if this occurs.

- **Permission Errors on macOS**:

  If you encounter permission issues on macOS, grant execution permissions to ChromeDriver:
  ```bash
  chmod +x venv/bin/chromedriver
  ```

- **Session Cookie Issues**:

  If the AI Applier doesn’t seem to remember the login, ensure cookies are correctly saved in the initial session. Restart the AI Applier if needed.

- **Application Logs**:

  Review `application_log.txt` to troubleshoot failed applications. Errors are logged with timestamps to assist in debugging.

This setup ensures a secure and reliable experience for automating job applications on Xing. Adjust configuration options as needed and refer to the logs for a complete record of all applied jobs and any encountered issues.

---

## License

This project is licensed under the MIT License.
