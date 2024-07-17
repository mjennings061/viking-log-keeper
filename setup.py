"""setup.py - This file is used to install the package and its dependencies."""

import shutil
import logging
from setuptools import setup, find_packages
from setuptools.command.install import install
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)


def parse_requirements(filename):
    """Parse the requirements file."""
    req_path = Path(__file__).parent / filename
    with open(req_path, 'r') as file:
        return file.read().splitlines()


class PostInstallCommand(install):
    """Install the package and run a post-installation script."""
    def run(self):
        """Run the post-installation script."""
        logging.info("Running post-installation script.")
        install.run(self)
        self.post_install()

    def post_install(self):
        """Run after the package is installed."""
        # Create the a run script for the user.
        try:
            logging.info("Attempting to copy bat file.")
            self.copy_bat_file()
        except Exception:   # pylint: disable=broad-except
            logging.error("Could not create bat file.")

    def copy_bat_file(self):
        """Create a .bat file that will run the update-logs command."""
        # Constants.
        BAT_FILE_NAME = 'run_log_keeper.bat'

        # Define the source and destination paths
        source = Path(__file__).parent / 'log_keeper' / 'scripts' / \
            BAT_FILE_NAME

        # Find the desktop. If the user has OneDrive, use that instead.
        desktop = Path.home() / 'Desktop'
        onedrive_desktop = Path.home() / 'OneDrive' / 'Desktop'
        if desktop.exists():
            desktop = desktop
        elif onedrive_desktop.exists():
            desktop = onedrive_desktop
        else:
            logging.warning("Could not find desktop or OneDrive Desktop.")
            raise FileNotFoundError("Could not find desktop.")

        # Copy the .bat file to the user's home directory
        destination = desktop / BAT_FILE_NAME
        shutil.copyfile(source, destination)
        logging.info('%s has been copied to %s', BAT_FILE_NAME, str(desktop))


setup(
    name="viking-log-keeper",
    version="1.5.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    url="https://github.com/mjennings061/viking-log-keeper",
    license="MIT",
    author="Michael Jennings",
    author_email="mjennings061@gmail.com",
    description="661 VGS - Function to collate 2965D log sheets into a"
                " master log, database, and dashboard.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    cmdclass={
        'install': PostInstallCommand,
    },
    include_package_data=True,
    data_files=[('', ['requirements.txt'])],
    install_requires=parse_requirements('requirements.txt'),
    entry_points={
        "console_scripts": [
            "update-logs=log_keeper.main:main",
            "update-config=dashboard.auth:update_credentials_wrapper",
            "update-log-sheet-location=log_keeper.get_config:"
            "update_log_sheets_dir_wrapper",
            "viking-dashboard=dashboard.main:display_dashboard"
        ]
    },
)
