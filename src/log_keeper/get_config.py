"""get_config.py - Get the database configuration from keyring"""

# Get packages.
from pathlib import Path
from dataclasses import dataclass
import inquirer
import keyring
import logging

# Get packages from the log_keeper package.
from log_keeper.utils import PROJECT_NAME

# Set up logging.
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Data class to store the configuration values."""
    # Get the credentials from the keyring.
    # Note: The keyring returns None if the key is not found.
    logger.info("Loading config...")
    db_hostname: str = keyring.get_password(PROJECT_NAME, "db_hostname")
    db_username: str = keyring.get_password(PROJECT_NAME, "db_username")
    db_password: str = keyring.get_password(PROJECT_NAME, "db_password")
    db_name: str = keyring.get_password(PROJECT_NAME, "db_name")
    db_collection_name: str = keyring.get_password(PROJECT_NAME,
                                                   "db_collection_name")
    log_sheets_dir: str = keyring.get_password(PROJECT_NAME, "log_sheets_dir")

    def validate(self):
        """Validate the configuration values."""
        # Check if any of the values are None.
        if not all([self.db_hostname, self.db_username, self.db_password,
                    self.db_name, self.db_collection_name,
                    self.log_sheets_dir]):
            logger.warning("Configuration values are missing.")
            return False
        # Check if the log_sheets_dir is a directory.
        if not Path(self.log_sheets_dir).is_dir():
            logger.warning("Invalid log sheets directory: %s",
                           self.log_sheets_dir)
            return False
        logger.info("Config valid.")
        return True

    def save_credentials(self):
        """Save the credentials to the keyring."""
        logger.info("Saving credentials to keyring.")
        keyring.set_password(PROJECT_NAME, "db_hostname", self.db_hostname)
        keyring.set_password(PROJECT_NAME, "db_username", self.db_username)
        keyring.set_password(PROJECT_NAME, "db_password", self.db_password)
        keyring.set_password(PROJECT_NAME, "db_name", self.db_name)
        keyring.set_password(PROJECT_NAME, "db_collection_name",
                             self.db_collection_name)
        keyring.set_password(PROJECT_NAME, "log_sheets_dir",
                             self.log_sheets_dir)
        logger.info("Credentials saved.")

    def get_credentials_cli(self):
        """Get the encrypted credentials using the CLI."""
        questions = [
            inquirer.Text(
                "db_hostname",
                message="Database hostname e.g. 666vgs.pda4bch.mongodb.net"
            ),
            inquirer.Text(
                "db_username",
                message="Database username e.g. 666vgs"
            ),
            inquirer.Text(
                "db_password",
                message="Database password e.g. vigilants_are_better"
            ),
            inquirer.Text(
                "db_name",
                message="Database name e.g. 666vgs"
            ),
            inquirer.Text(
                "db_collection_name",
                message="Database collection name e.g. log_sheets"
            ),
            inquirer.Text(
                "log_sheets_dir",
                message="Enter the path to the Documents directory " +
                        "e.g. C:\\Users\\YOUR_USERNAME\\OneDrive\\Documents\n",
                validate=lambda _, x: Path(x).is_dir(
                ) or "Path does not exist or is not a directory.",
            )
        ]

        # Display the questions.
        answers = inquirer.prompt(questions)
        return answers

    def update_credentials(self):
        """Update the credentials."""
        # Get the credentials using CLI.
        credentials = self.get_credentials_cli()
        self.db_hostname = credentials["db_hostname"]
        self.db_username = credentials["db_username"]
        self.db_password = credentials["db_password"]
        self.db_name = credentials["db_name"]
        self.db_collection_name = credentials["db_collection_name"]
        self.log_sheets_dir = credentials["log_sheets_dir"]
        self.save_credentials()

    def update_log_sheets_dir(self):
        """Update the log sheets directory."""
        # Get the log sheets directory using CLI.
        logging.info("Updating log sheets directory.")
        questions = [
            inquirer.Text(
                "log_sheets_dir",
                message="Enter the path to the Documents directory " +
                        "e.g. C:\\Users\\YOUR_USERNAME\\OneDrive\\Documents\n",
                validate=lambda _, x: Path(x).is_dir(
                ) or "Path does not exist or is not a directory.",
            )
        ]
        answers = inquirer.prompt(questions)
        self.log_sheets_dir = answers["log_sheets_dir"]
        self.save_credentials()


def update_log_sheets_dir_wrapper():
    """Wrapper function to update the log sheets directory."""
    config = Config()
    config.update_log_sheets_dir()


def update_credentials_wrapper():
    """Wrapper function to update the credentials."""
    config = Config()
    config.update_credentials()


if __name__ == "__main__":
    # Get the config file.
    config = Config()
    print(config)
