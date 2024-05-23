"""setup.py - This file is used to install the package and its dependencies."""

import shutil
from setuptools import setup, find_packages
from setuptools.command.install import install
from pathlib import Path


class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        print("Running post-installation script.")
        print("Running post-installation script.")
        install.run(self)
        self.post_install()

    def post_install(self):
        """Run after the package is installed."""
        # Create the a run script for the user.
        try:
            self.copy_bat_file()
        except Exception:   # pylint: disable=broad-except
            print("Could not create bat file.")

    def copy_bat_file():
        """Create a .bat file that will run the update-logs command."""
        # Define the source and destination paths
        source = Path(__file__).parent / 'scripts' / 'run_log_keeper.bat'
        desktop = Path.home() / 'Desktop'
        destination = desktop / 'run_log_keeper.bat'

        # Copy the .bat file to the user's home directory
        shutil.copyfile(source, destination)
        print(f'run_log_keeper.bat has been copied to {destination}')


setup(
    name="viking-log-keeper",
    version="1.3.0",
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
    package_data={'': ['scripts/*.bat']},
    install_requires=[
        "extra-streamlit-components>=0.1.70",
        "inquirer>=3.2.0",
        "keyring>=24.3.0",
        "logging>=0.4.9.0",
        "matplotlib>=3.8.0",
        "openpyxl>=3.1.0",
        "pandas>=2.2.0",
        "pymongo[srv]>=4.6.0",
        "streamlit>=1.32.0",
        "tqdm>=4.66.0",
        "xlsxwriter>=3.2.0"
    ],
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
