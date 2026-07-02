"""conftest.py - Configuration for pytest."""

import sys
from pathlib import Path

import pytest

# Add the src directory to the Python path
src_dir = str(Path(__file__).parent.parent / "src")
sys.path.append(src_dir)


# The e2e test hits the self-signed server with verify=False; match by message.
def pytest_configure(config):
    config.addinivalue_line("filterwarnings", "ignore:Unverified HTTPS request")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # E2E server uses a self-signed cert (needed so Secure cookies are stored).
    return {**browser_context_args, "ignore_https_errors": True}
