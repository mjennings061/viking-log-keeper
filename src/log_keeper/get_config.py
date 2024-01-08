"""get_config.py

Get the database configuration from a config file."""

from pathlib import Path
from dotenv import dotenv_values
from cryptography.fernet import Fernet
import inquirer


def get_key():
    """Get the secret key for encrypting the credentials.

    Returns:
        Fernet: The secret key used for encryption.
    """
    # Key file.
    KEY_FILE = "secret.key"

    # Check if the key file exists.
    if Path(KEY_FILE).is_file():
        # Get the key from the file.
        with open(KEY_FILE, 'rb') as key_file:
            secret_key = key_file.read()
    else:
        # Generate a key and save it to a file.
        secret_key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as key_file:
            key_file.write(secret_key)
    return secret_key


def encrypt_data(data, secret_key):
    """
    Encrypts the data using the provided secret key.

    Args:
        data (str): The data to be encrypted.
        secret_key (Fernet): The secret key used for encryption.

    Returns:
        Fernet: The encrypted data.
    """
    cipher_suite = Fernet(secret_key)
    encrypted_data = cipher_suite.encrypt(data.encode())
    return encrypted_data


def decrypt_data(encrypted_data, secret_key):
    """
    Decrypt the data using the secret key.

    Args:
        encrypted_data (str): The encrypted data to be decrypted.
        secret_key (Fernet): The secret key used for decryption.

    Returns:
        Fernet: The decrypted data.
    """
    cipher_suite = Fernet(secret_key)
    decrypted_data = cipher_suite.decrypt(encrypted_data.encode())
    return decrypted_data


def get_credentials_cli():
    """
    Use inquirer to get the encrypted credentials CLI.

    Returns:
        dict: A dictionary containing the user's input for database
            hostname, username, password, collection name, and database name.
    """
    # Get the credentials using CLI.
    questions = [
        inquirer.Text(
            "DB_HOSTNAME",
            message="Database hostname e.g. 666vgs.pda4bch.mongodb.net"
        ),
        inquirer.Text(
            "DB_USERNAME",
            message="Database username e.g. 666vgs"
        ),
        inquirer.Text(
            "DB_PASSWORD",
            message="Database password e.g. vigilants_are_better"
        ),
        inquirer.Text(
            "DB_NAME",
            message="Database name e.g. 666vgs"
        ),
        inquirer.Text(
            "DB_COLLECTION_NAME",
            message="Database collection name e.g. log_sheets"
        ),
    ]

    # Display the questions.
    answers = inquirer.prompt(questions)
    return answers


def remove_config():
    """Remove the config file.

    This function removes the config file if it exists.
    The config file path is obtained by resolving the parent directory
    of the current file and appending the name of the config file.

    Args:
        None

    Returns:
        None
    """
    # Get the config file path.
    DB_CONFIG_FILE = ".env"
    config_filepath = Path(__file__).resolve().parent / DB_CONFIG_FILE

    # Check if a config file exists.
    if config_filepath.is_file():
        # Remove the config file.
        config_filepath.unlink()


def get_config():
    """Get the config file path and return the configuration as a dictionary.

    If the config file does not exist, it prompts the user to enter
    the configuration values through the command-line interface (CLI)
    and creates the config file.
    If the config file exists, it reads the encrypted values from the
    file, decrypts them using a secret key, and returns the configuration
    as a dictionary.

    Returns:
        dict: The configuration values as a dictionary.

    """
    # Get the config file path.
    DB_CONFIG_FILE = ".env"
    config_filepath = Path(__file__).resolve().parent / DB_CONFIG_FILE

    # Check if a config file exists.
    if not config_filepath.is_file():
        # Use CLI to create a config file.
        config = get_credentials_cli()

        # Create a secret key.
        secret_key = get_key()

        # Write the config file.
        with open(config_filepath, "w") as f:
            for key, value in config.items():   # type: ignore
                encrypted_value = encrypt_data(value, secret_key)
                f.write(f"{key}={encrypted_value.decode()}\n")

    else:
        # Read the config file.
        config_encrypted = dotenv_values(config_filepath)

        # Get the secret key.
        secret_key = get_key()

        # Decrypt the credentials.
        config = {}
        for key, value in config_encrypted.items():
            decrypted_value = decrypt_data(value, secret_key)
            config[key] = decrypted_value.decode()

    return config


if __name__ == "__main__":
    get_config()
