from pathlib import Path
from dotenv import dotenv_values
from cryptography.fernet import Fernet
import inquirer

def get_key():
    """Get the secret key for encrypting the credentials."""
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
    """Encrypt the data using the secret key."""
    cipher_suite = Fernet(secret_key)
    encrypted_data = cipher_suite.encrypt(data.encode())
    return encrypted_data


def decrypt_data(encrypted_data, secret_key):
    """Decrypt the data using the secret key."""
    cipher_suite = Fernet(secret_key)
    decrypted_data = cipher_suite.decrypt(encrypted_data.encode())
    return decrypted_data


def get_credentials_cli():
    """Use inquirer to get the encrypted credentials CLI."""
    # Get the credentials using CLI.
    questions = [
        inquirer.Text("DB_HOSTNAME", message="Database hostname e.g. 666vgs.pda4bch.mongodb.net"),
        inquirer.Text("DB_USERNAME", message="Database username e.g. 666vgs"),
        inquirer.Text("DB_PASSWORD", message="Database password e.g. vigilants_are_better"),
        inquirer.Text("DB_COLLECTION_NAME", message="Database collection name"),
        inquirer.Text("DB_NAME", message="Database name:"),
    ]
    answers = inquirer.prompt(questions)
    return answers


def remove_config():
    """Remove the config file."""
    # Get the config file path.
    DB_CONFIG_FILE = ".env"
    config_filepath = Path(__file__).resolve().parent / DB_CONFIG_FILE

    # Check if a config file exists.
    if config_filepath.is_file():
        # Remove the config file.
        config_filepath.unlink()


def get_config():
    """Get the config file path."""
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