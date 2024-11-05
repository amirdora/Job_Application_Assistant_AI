# platforms/base.py

import os
import pickle
from selenium import webdriver
from abc import ABC, abstractmethod
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

class JobPlatform(ABC):
    platform_name = "undefined"  # Default value

    def __init__(self, config, headless=True):
        self.config = config
        self.cookies_file = f"cookies/{self.platform_name}.pkl"
        self.applications = []
        self.browser = self.start_browser(headless)

    def start_browser(self, headless=True):
        """Initialize the Chrome WebDriver with options."""
        options = webdriver.ChromeOptions()
        if headless:
            options.headless = True
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    @abstractmethod
    def login(self):
        pass

    @abstractmethod
    def construct_search_url(self):
        pass

    @abstractmethod
    def apply_jobs(self):
        pass

    def load_cookies(self):
        """Load cookies from a saved file."""
        if os.path.exists(self.cookies_file):
            self.browser.get(self.base_url)
            with open(self.cookies_file, "rb") as file:
                cookies = pickle.load(file)
                for cookie in cookies:
                    if "domain" in cookie:
                        del cookie["domain"]
                    self.browser.add_cookie(cookie)
            return True
        return False

    def save_cookies(self):
        """Save cookies to a file for future sessions."""
        with open(self.cookies_file, "wb") as file:
            pickle.dump(self.browser.get_cookies(), file)
