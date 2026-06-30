"""test_dashboard_e2e.py - End-to-end tests for critical user flows.

These tests use Playwright for full browser testing of critical user journeys.
Use these sparingly for flows that absolutely require browser rendering.
"""

import os
import re
import subprocess
import time

import pytest
import requests
from dotenv import load_dotenv
from playwright.sync_api import Page, expect

# Load environment variables
load_dotenv()
USERNAME = str(os.getenv("TEST_USERNAME"))
PASSWORD = str(os.getenv("TEST_PASSWORD"))

BASE_URL = "http://localhost:8501"


@pytest.fixture(scope="session", autouse=True)
def streamlit_app():
    """Start Streamlit app for E2E tests (simplified version).

    This fixture starts the Streamlit app once per test session and cleans up
    after all tests complete. pytest-playwright handles browser lifecycle.
    """
    # Kill any existing Streamlit processes
    try:
        subprocess.run(
            ["pkill", "-f", "streamlit.*8501"],
            check=False,
            timeout=5,
            capture_output=True,
        )
        time.sleep(2)  # Wait for port to be freed
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Start Streamlit
    streamlit_process = subprocess.Popen(
        [
            "streamlit",
            "run",
            "src/dashboard/main.py",
            "--server.port=8501",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--server.enableCORS=false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for Streamlit to be ready
    max_wait_time = 30
    start_time = time.time()
    ready = False

    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get(BASE_URL, timeout=3)
            if response.status_code == 200:
                ready = True
                break
        except (requests.ConnectionError, requests.Timeout):
            pass

        # Check if process died
        if streamlit_process.poll() is not None:
            stdout, stderr = streamlit_process.communicate()
            pytest.fail(
                f"Streamlit process died. "
                f"STDOUT: {stdout.decode()}, STDERR: {stderr.decode()}"
            )

        time.sleep(1)

    if not ready:
        streamlit_process.kill()
        stdout, stderr = streamlit_process.communicate()
        pytest.fail(
            f"Streamlit failed to start. "
            f"STDOUT: {stdout.decode()}, STDERR: {stderr.decode()}"
        )

    # Give it a moment to fully initialise
    time.sleep(2)

    yield

    # Cleanup
    streamlit_process.terminate()
    try:
        streamlit_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        streamlit_process.kill()

    # Final cleanup
    try:
        subprocess.run(
            ["pkill", "-f", "streamlit.*8501"],
            check=False,
            timeout=5,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def login_user(page: Page) -> None:
    """Helper function to log in a user.

    Args:
        page: Playwright page instance
    """
    page.goto(BASE_URL)

    # Fill login form
    page.get_by_label("Username", exact=True).fill(USERNAME)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_test_id("stBaseButton-secondaryFormSubmit").click()

    # Wait for dashboard to load
    expected_heading = f"{USERNAME.upper()} Dashboard"
    expect(page.get_by_role("heading", name=expected_heading)).to_be_visible(
        timeout=10000
    )


#####################################################################
# E2E Test Functions
#####################################################################


def test_root_page_loads(page: Page):
    """Test that the root page loads and shows login form."""
    page.goto(BASE_URL)
    expect(page.get_by_test_id("stForm")).to_be_visible()


def test_login_with_invalid_credentials(page: Page):
    """Test that login fails with incorrect credentials."""
    page.goto(BASE_URL)

    page.get_by_label("Username", exact=True).fill(USERNAME)
    page.get_by_label("Password", exact=True).fill("wrong_password")
    page.get_by_test_id("stBaseButton-secondaryFormSubmit").click()

    # Should show error message
    expect(page.get_by_text("Invalid Password")).to_be_visible(timeout=10000)


def test_complete_login_flow(page: Page):
    """Test complete user login flow (critical path)."""
    login_user(page)

    # Verify dashboard is loaded
    expected_heading = f"{USERNAME.upper()} Dashboard"
    expect(page.get_by_role("heading", name=expected_heading)).to_be_visible()

    # Verify we can refresh data (confirms dashboard is functional)
    expect(page.get_by_test_id("stBaseButton-secondary")).to_be_visible()


def test_dashboard_data_refresh(page: Page):
    """Test that data refresh works on dashboard."""
    login_user(page)

    # Click refresh button
    page.get_by_test_id("stBaseButton-secondary").click()

    # Look for success message
    expect(page.get_by_text("Data Refreshed!")).to_be_visible()


def test_navigation_to_upload_page(page: Page):
    """Test navigation to upload page (critical user flow)."""
    login_user(page)

    # Navigate to upload page
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("📁 Log Sheets").click()

    # Verify upload page loaded. The page has two uploaders (template +
    # completed log sheets); the completed-log-sheets one renders last.
    expect(page.get_by_test_id("stFileUploaderDropzone").last).to_be_visible()


def navigate_to_stats_gur_page(page: Page) -> None:
    """Helper to open the Stats & GUR page."""
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("🧮 Stats & GUR Helper").click()
    expect(page.get_by_role("heading", name="Stats Helpers")).to_be_visible(
        timeout=10000
    )


def test_navigation_to_stats_gur_page(page: Page):
    """Test the Stats & GUR page shows the ops form helper by default."""
    login_user(page)
    navigate_to_stats_gur_page(page)

    # The ops form helper is shown by default; detail tables are hidden.
    expect(page.get_by_role("link", name="📝 Open Stats Return Form")).to_be_visible()
    expect(page.get_by_text("Show more stats")).to_be_visible()
    expect(page.get_by_role("heading", name="GUR Helpers")).to_be_visible()


def test_show_more_stats_reveals_tables(page: Page):
    """Test clicking 'Show more stats' reveals the detail tables."""
    login_user(page)
    navigate_to_stats_gur_page(page)

    # Tables are hidden until the toggle is clicked.
    expect(page.get_by_role("heading", name="First & Last Launch Times")).to_be_hidden()

    # The visible switch is the clickable label; the input itself is hidden.
    page.get_by_text("Show more stats").click()

    expect(
        page.get_by_role("heading", name="First & Last Launch Times")
    ).to_be_visible()
    expect(page.get_by_role("heading", name="Launches by Type")).to_be_visible()


def test_navigation_to_weather_page(page: Page):
    """Test navigation to weather page."""
    login_user(page)

    # Open Statistics dropdown and navigate to Weather page
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("⛅ Weather").click()

    # Wait for weather page to load
    expect(page.get_by_role("heading", name="Weather Summary")).to_be_visible(
        timeout=10000
    )


def test_weather_variable_selection(page: Page):
    """Test changing weather variable display."""
    login_user(page)

    # Navigate to weather page
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("⛅ Weather").click()

    # Change weather variable
    page.locator("div").filter(has_text=re.compile(r"^Wind Speed$")).first.click()
    page.get_by_role("option", name="Wind Direction").click()

    # Verify change was applied (page should not error)
    expect(page.get_by_role("heading", name="Weather Summary")).to_be_visible()


def test_weather_cache_reload(page: Page):
    """Test weather data cache reload functionality."""
    login_user(page)

    # Navigate to weather page
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("⛅ Weather").click()

    # Click reload button
    page.get_by_test_id("stBaseButton-secondary").click()

    # Verify reload success message
    expect(page.get_by_text("Weather data fetched successfully.")).to_be_visible(
        timeout=10000
    )


def test_pilot_filter_functionality(page: Page):
    """Test pilot filtering on dashboard (critical user flow)."""
    login_user(page)

    # Use pilot filter
    expect(page.get_by_text("Filter by Pilot")).to_be_visible()
    page.locator("div").filter(has_text=re.compile(r"^All$")).first.click()
    page.get_by_test_id("stSelectboxVirtualDropdown").get_by_text("Jennings").click()

    # Use quarter filter
    expect(page.get_by_text("Select QuarterChoose an")).to_be_visible()
    page.locator("div").filter(has_text=re.compile(r"^Choose an option$")).first.click()

    # Select first available quarter
    page.get_by_test_id("stSelectboxVirtualDropdown").get_by_role(
        "option"
    ).first.click()

    # Verify quarterly summary appears
    expect(page.get_by_role("heading", name="Quarterly Summary Helper")).to_be_visible()


def test_file_upload_valid(page: Page):
    """Test uploading a valid Excel log sheet."""
    login_user(page)

    # Navigate to upload page
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("📁 Log Sheets").click()
    expect(page.get_by_test_id("stFileUploaderDropzone").last).to_be_visible()

    # Upload valid file to the completed-log-sheets uploader (the last one).
    valid_file = "tests/fixtures/2965D_260214_ZE633.xlsx"
    page.locator("input[type='file']").last.set_input_files([valid_file])

    # Assert success message appears in toast notification
    expect(
        page.get_by_test_id("stToastContainer").get_by_text("Log Sheets Uploaded!")
    ).to_be_visible(timeout=15000)


def test_file_upload_invalid(page: Page):
    """Test uploading an invalid Excel file shows warning."""
    login_user(page)

    # Navigate to upload page
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("📁 Log Sheets").click()
    expect(page.get_by_test_id("stFileUploaderDropzone").last).to_be_visible()

    # Upload invalid xlsx file (has .xlsx extension but is not a valid Excel file)
    invalid_file = "tests/fixtures/invalid.xlsx"
    page.locator("input[type='file']").last.set_input_files([invalid_file])

    # Assert warning message appears indicating the log sheet is invalid
    expect(
        page.get_by_text(re.compile(r"Log sheet invalid.*invalid\.xlsx"))
    ).to_be_visible(timeout=10000)
