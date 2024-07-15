"""gui.py - Flet-based GUI for the log_keeper application."""

# Import modules.
import sys
import logging
from typing import Optional
from pathlib import Path
import flet as ft


# Get modules.
def get_base_path():
    """Get the base path of the application. This is required to load the
    user-defined modules when the application is frozen e.g. using build.

    Returns:
        Path: The base path of the application."""
    if getattr(sys, 'frozen', True):
        # If the application is frozen, use this path
        return Path(sys.executable).parent
    else:
        # If not frozen, use the script location
        return Path(__file__).resolve().parents[1]


# Import user-defined modules.
base_path = get_base_path()
sys.path.append(str(base_path))
from log_keeper.main import update_logs_wrapper  # noqa: E402
from log_keeper.get_config import LogSheetConfig  # noqa: E402
from dashboard.auth import authenticate_log_sheet_db  # noqa: E402
from dashboard.auth import update_credentials_wrapper  # noqa: E402

print(f"Base path: {base_path}")
print(f"sys.path: {sys.path}")

# Set logging level.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_config() -> Optional[LogSheetConfig]:
    """Fetch the configuration."""
    db_config = authenticate_log_sheet_db()
    return db_config


def main(page: ft.Page):
    page.title = "Log Keeper GUI"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    log_output = ft.TextField(multiline=True, width=600, height=300)

    def update_logs(e):
        try:
            log_output.value += "Starting log update...\n"
            update_logs_wrapper()
            log_output.value += "Log update successful!\n"
        except Exception as ex:
            log_output.value += f"Error: {str(ex)}\n"
        page.update()

    def update_credentials(e):
        try:
            log_output.value += "Updating credentials...\n"
            update_credentials_wrapper()
            log_output.value += "Credentials updated successfully!\n"
        except Exception as ex:
            log_output.value += f"Error: {str(ex)}\n"
        page.update()

    # Create the buttons.
    update_logs_button = ft.ElevatedButton(
        text="Update Logs",
        on_click=update_logs
    )
    update_credentials_button = ft.ElevatedButton(
        text="Update Credentials",
        on_click=update_credentials
    )

    # Add all the elements to the page.
    page.add(
        ft.Column(
            [
                update_logs_button,
                update_credentials_button,
                log_output,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )


if __name__ == "__main__":
    # Run the Flet app.
    ft.app(target=main)
