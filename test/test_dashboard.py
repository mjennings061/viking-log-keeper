"""test_dashboard.py - Test cases for the dashboard module."""

import os
import pytest
import subprocess
import time
from dotenv import load_dotenv
from pathlib import Path
from playwright.sync_api import Page, expect

# Load environment variables
load_dotenv()
dashboard_username = os.getenv("DASHBOARD_USERNAME")
dashboard_password = os.getenv("DASHBOARD_PASSWORD")


# Function to start Streamlit
@pytest.fixture(scope="session", autouse=True)
def start_streamlit():
    # Replace with your actual Streamlit script path and command
    path_to_streamlit_script = Path(__file__).parent.parent \
        / "src" / "dashboard" / "main.py"
    streamlit_command = ["streamlit", "run", str(path_to_streamlit_script)]
    streamlit_process = subprocess.Popen(streamlit_command)

    # Wait for Streamlit to start.
    wait_time = 3
    start_time = time.time()
    while time.time() < start_time + wait_time:
        time.sleep(1)
    yield

    # Teardown code if needed.
    streamlit_process.terminate()
    streamlit_process.wait(timeout=5)


@pytest.fixture(scope="function")
def setup(page: Page):
    page.goto("http://localhost:8501")
    yield page
    # Close the page after the test.
    page.close()


@pytest.fixture(scope="function")
def login(setup: Page):
    page = setup
    page.get_by_label("Username").click()
    page.get_by_label("Username").fill(dashboard_username)
    page.get_by_label("Password", exact=True).click()
    page.get_by_label("Password", exact=True).fill(dashboard_password)
    page.get_by_test_id("baseButton-secondaryFormSubmit").click()
    yield page
    # Close the page after the test.
    page.close()


def test_root_page(setup: Page):
    # Check if the root page is loaded.
    page = setup
    expect(page.get_by_test_id("stForm")).to_be_visible()


def test_dashboard_login(login: Page):
    # Check if the dashboard page is loaded after login.
    page = login

    # Check if the dashboard page is loaded after login.
    expect(page.get_by_role(
        "heading", name="661VGS Dashboard"
    )).to_be_visible()


def test_example(login: Page) -> None:
    page = login
    page.get_by_role("img", name="open").first.click()
    page.get_by_text("🌍 All Data").click()
    expect(page.locator(".dvn-scroller")).to_be_visible()


if __name__ == "__main__":
    pytest.main()
