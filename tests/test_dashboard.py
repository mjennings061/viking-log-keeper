"""test_dashboard.py - Test cases for the dashboard module."""

import os
import re
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from playwright.sync_api import Page, expect
from requests.exceptions import ConnectionError

# Load environment variables
load_dotenv()
USERNAME = str(os.getenv("TEST_USERNAME"))
PASSWORD = str(os.getenv("TEST_PASSWORD"))


#####################################################################
# Test fixtures.
# Function to start Streamlit before running tests.
@pytest.fixture(scope="session", autouse=True)
def start_streamlit():
    """Start Streamlit before running tests and wait for it to be ready."""
    # Kill any existing Streamlit processes on port 8501
    try:
        subprocess.run(["pkill", "-f", "streamlit.*8501"], check=False, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Wait for port to be free
    max_cleanup_time = 10
    start_time = time.time()
    while time.time() - start_time < max_cleanup_time:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", 8501)) != 0:
                break
        time.sleep(0.5)
    else:
        pytest.fail("Port 8501 is still in use after cleanup attempt")

    # Additional cleanup wait
    time.sleep(2)

    # Get path to Streamlit script.
    path_to_streamlit_script = (
        Path(__file__).parent.parent / "src" / "dashboard" / "main.py"
    )

    # Verify the main.py file exists
    if not path_to_streamlit_script.exists():
        pytest.fail(f"Streamlit script not found at {path_to_streamlit_script}")

    # Start Streamlit with explicit port and configuration
    streamlit_command = [
        "streamlit",
        "run",
        str(path_to_streamlit_script),
        "--server.port=8501",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
    ]

    # Start process with proper environment
    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"

    streamlit_process = subprocess.Popen(
        streamlit_command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,  # Create new process group
    )

    # Wait for Streamlit to start by polling the URL.
    max_wait_time = 10  # Increased timeout for robustness
    start_time = time.time()
    url = "http://localhost:8501"
    ready = False
    last_error = None

    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                ready = True
                break
        except (
            ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
        ) as e:
            last_error = str(e)
            # Server is not ready yet or having issues
            pass

        # Check if process is still alive
        if streamlit_process.poll() is not None:
            stdout, stderr = streamlit_process.communicate()
            error_msg = (
                f"Streamlit process died unexpectedly. "
                f"STDOUT: {stdout.decode()}, "
                f"STDERR: {stderr.decode()}"
            )
            pytest.fail(error_msg)

        time.sleep(1)  # Increased polling interval

    if not ready:
        # Capture output for debugging
        try:
            stdout, stderr = streamlit_process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            streamlit_process.kill()
            stdout, stderr = streamlit_process.communicate()

        # Kill process group to ensure cleanup
        try:
            os.killpg(os.getpgid(streamlit_process.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

        error_msg = (
            f"Streamlit failed to start within {max_wait_time} "
            f"seconds. Last error: {last_error}, "
            f"STDOUT: {stdout.decode()}, "
            f"STDERR: {stderr.decode()}"
        )
        pytest.fail(error_msg)

    # Give Streamlit a moment to fully initialize
    time.sleep(2)
    yield

    # Teardown code: terminate the Streamlit process group.
    try:
        # First try graceful termination
        os.killpg(os.getpgid(streamlit_process.pid), signal.SIGTERM)
        streamlit_process.wait(timeout=10)
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        # Force kill if graceful termination fails
        try:
            os.killpg(os.getpgid(streamlit_process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    # Additional cleanup - kill any remaining streamlit processes
    try:
        subprocess.run(["pkill", "-f", "streamlit.*8501"], check=False, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


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
    page.get_by_label("Username").fill(USERNAME)
    page.get_by_label("Password", exact=True).click()
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_test_id("stBaseButton-secondaryFormSubmit").click()
    yield page
    # Close the page after the test.
    page.close()


@pytest.fixture(scope="function")
def upload_page(login: Page):
    """Navigate to the upload page for each test."""
    page = login
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("📁 Upload Log Sheets").click()
    yield page


@pytest.fixture(scope="function")
def stats_gur_page(login: Page):
    """Navigate to the stats and GUR page for each test."""
    page = login
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("🧮 Stats & GUR Helper").click()
    yield page


@pytest.fixture(scope="function")
def weather_page(login: Page):
    """Navigate to the weather page for each test."""
    page = login
    page.locator("div").filter(has_text=re.compile(r"^📈 Statistics$")).first.click()
    page.get_by_text("⛅ Weather").click()
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
    page.get_by_label("Username").fill(USERNAME)
    page.get_by_label("Password", exact=True).click()
    page.get_by_label("Password", exact=True).fill("test")
    page.get_by_test_id("stBaseButton-secondaryFormSubmit").click()

    # Check if the invalid password message is displayed.
    expect(page.get_by_text("Invalid Password")).to_be_visible(timeout=10000)


def test_dashboard_login(login: Page):
    """Check if the dashboard page is loaded after login."""
    page = login

    # Check if the dashboard page is loaded after login.
    dummy_user = USERNAME.upper()
    expected_heading = f"{dummy_user} Dashboard"
    expect(page.get_by_role("heading", name=expected_heading)).to_be_visible()
    expect(page.get_by_role("heading", name=expected_heading)).to_be_visible()


def test_refresh_data(login: Page):
    """Check if the data is refreshed after clicking the refresh button."""
    page = login
    page.get_by_test_id("stBaseButton-secondary").click()

    # Look for the toast message.
    expect(page.get_by_text("Data Refreshed!")).to_be_visible()


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
    expect(page.get_by_role("heading", name="Stats Helpers")).to_be_visible()
    expect(
        page.get_by_role("heading", name="First & Last Launch Times")
    ).to_be_visible()
    expect(page.get_by_role("heading", name="Launches by Type")).to_be_visible()
    expect(page.get_by_role("heading", name="GUR Helpers")).to_be_visible()
    expect(
        page.get_by_role("heading", name="Weekly Summary by Aircraft")
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="Daily Summary by Aircraft")
    ).to_be_visible()


def test_change_page_to_weather(weather_page: Page):
    """Check if the page changes after clicking the 'Weather' button."""
    page = weather_page

    # Check if the weather page is loaded.
    expect(page.get_by_role("heading", name="Weather Summary")).to_be_visible()

    # Change variable to display.
    page.locator("div").filter(has_text=re.compile(r"^Wind Speed$")).first.click()
    page.get_by_role("option", name="Wind Direction").click()


def test_weather_reload_cache(weather_page: Page):
    """Check if the weather data is reloaded after clicking
    the refresh button."""
    page = weather_page
    page.get_by_test_id("stBaseButton-secondary").click()

    # Check if the data has been reloaded.
    expect(page.get_by_text("Weather data fetched successfully.")).to_be_visible(
        timeout=10000
    )


def test_aircraft_commander_filter(login: Page):
    """Check if the aircraft commander filter works."""
    page = login

    # Use aircraft commander filter.
    expect(page.get_by_text("Filter by Pilot")).to_be_visible()
    page.locator("div").filter(has_text=re.compile(r"^All$")).first.click()
    page.get_by_test_id("stSelectboxVirtualDropdown").get_by_text("Jennings").click()

    # User quarter filter.
    expect(page.get_by_text("Select QuarterChoose an")).to_be_visible()
    page.locator("div").filter(has_text=re.compile(r"^Choose an option$")).first.click()
    page.get_by_text("2025Q2").click()

    # Check if the quarterly filter has been displayed.
    expect(page.get_by_role("heading", name="Quarterly Summary Helper")).to_be_visible()


if __name__ == "__main__":
    pytest.main()
