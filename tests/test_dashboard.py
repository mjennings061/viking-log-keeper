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


#####################################################################
# Test fixtures.
# Function to start Streamlit before running tests.
@pytest.fixture(scope="session", autouse=True)
def start_streamlit():
    """Start Streamlit before running tests."""
    # Get path to Streamlit script.
    path_to_streamlit_script = Path(__file__).parent.parent \
        / "src" / "dashboard" / "main.py"
    streamlit_command = ["streamlit", "run", str(path_to_streamlit_script)]
    streamlit_process = subprocess.Popen(streamlit_command)

    # Wait for Streamlit to start.
    time.sleep(3)
    yield

    # Teardown code if needed.
    streamlit_process.terminate()
    streamlit_process.wait(timeout=5)


# Fixture to set up the page for each test.
@pytest.fixture(scope="function")
def setup(page: Page):
    """Set up the page for each test by navigating to the app."""
    page.goto("http://localhost:8501")
    yield page
    # Close the page after the test.
    page.close()


# Fixture to log in to the dashboard for each test.
@pytest.fixture(scope="function")
def login(setup: Page):
    """Log in to the dashboard for each test."""
    page = setup
    page.get_by_label("Username").click()
    page.get_by_label("Username").fill(dashboard_username)
    page.get_by_label("Password", exact=True).click()
    page.get_by_label("Password", exact=True).fill(dashboard_password)
    page.get_by_test_id("baseButton-secondaryFormSubmit").click()
    yield page
    # Close the page after the test.
    page.close()


@pytest.fixture(scope="function")
def upload_page(login: Page):
    """Navigate to the upload page for each test."""
    page = login
    page.get_by_test_id("stAppViewBlockContainer").get_by_role(
        "img",
        name="open"
    ).click()
    page.get_by_text("📁 Upload Log Sheets").click()
    yield page


@pytest.fixture(scope="function")
def stats_gur_page(login: Page):
    """Navigate to the stats and GUR page for each test."""
    page = login
    page.get_by_test_id("stAppViewBlockContainer").get_by_role(
        "img",
        name="open"
    ).click()
    page.get_by_text("🧮 Stats & GUR Helper").click()
    yield page


#####################################################################
# Test functions.
def test_root_page(setup: Page):
    """Check if the root page is loaded."""
    page = setup
    expect(page.get_by_test_id("stForm")).to_be_visible()


def test_login_incorrect_credentials(setup: Page):
    """Check if the login fails with incorrect credentials."""
    page = setup
    page.get_by_label("Username").click()
    page.get_by_label("Username").fill("test")
    page.get_by_label("Password", exact=True).click()
    page.get_by_label("Password", exact=True).fill("test")
    page.get_by_test_id("baseButton-secondaryFormSubmit").click()

    # Check if the invalid password message is displayed.
    expect(page.get_by_text("Invalid Password")).to_be_visible()


def test_dashboard_login(login: Page):
    """Check if the dashboard page is loaded after login."""
    page = login

    # Check if the dashboard page is loaded after login.
    # TODO: Add a dummy user and check for the user's name.
    expect(page.get_by_role(
        "heading", name="661VGS Dashboard"
    )).to_be_visible()


def test_refresh_data(login: Page):
    """Check if the data is refreshed after clicking the refresh button."""
    page = login
    page.get_by_test_id("baseButton-secondary").click()

    # Look for the toast message.
    expect(page.get_by_test_id("stToast")).to_be_visible()


def test_change_page(upload_page: Page):
    """Check if the page changes after clicking the 'Launches' button."""
    page = upload_page

    # Check if the upload page is loaded.
    expect(page.get_by_test_id("stFileUploaderDropzone")).to_be_visible()

# TODO: Add upload tests for a dummy DB user for:
# - Valid file upload
# - Invalid file upload
# - Check for new data after upload
# - Check for replaced data after upload


def test_change_page_to_stats_gur(stats_gur_page: Page):
    """Check if the page changes after clicking the 'Stats & GUR' button."""
    page = stats_gur_page

    # Check if the stats and GUR page is loaded.
    expect(
        page.get_by_role("heading", name="Stats Helpers")
        ).to_be_visible()
    expect(
        page.get_by_role("heading", name="First & Last Launch Times")
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="Launches by Type")
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="GUR")
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="Weekly Summary by Aircraft")
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="Daily Summary by Aircraft")
    ).to_be_visible()


if __name__ == "__main__":
    pytest.main()
