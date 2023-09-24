import os
import sys
import json
import subprocess
import logging
import requests
import shutil
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
import boto3

CONFIG_FILE = "backup_config.json"
LOG_FILE = "restore.log"

logger = logging.getLogger()
handler = RotatingFileHandler(LOG_FILE, maxBytes=1e6, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.ERROR)


def find_mariadb_credentials():
    standard_locations = [
        "/etc/my.cnf",
        "/etc/mysql/my.cnf",
        "~/.my.cnf",
    ]
    control_panel_locations = {
        "Plesk": "/etc/psa/.psa.shadow",
        "cPanel": "/root/.my.cnf",
        "CyberPanel": "/etc/cyberpanel/mysqlPassword",
        # Add other control panel-specific locations here
    }

    for location in standard_locations + list(control_panel_locations.values()):
        config_file = Path(location).expanduser()
        if config_file.exists():
            with open(config_file, 'r') as file:
                content = file.read()
                user_match = re.search(r"user\s*=\s*(\w+)", content)
                password_match = re.search(r"password\s*=\s*(\w+)", content)
                if user_match and password_match:
                    return user_match.group(1), password_match.group(1)
    return None, None

def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")


def send_pushover_message(token, user, message):
    url = "https://api.pushover.net/1/messages.json"
    data = {"token": token, "user": user, "message": message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to send Pushover message: {e}")


def database_exists(db, user, password):
    result = subprocess.run(["mysql", "-u", user, f"--password={password}", "-e", f"USE {db};"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0


def restore_backup(db, backup_path, user, password, config):
    try:
        if database_exists(db, user, password):
            overwrite = input(f"Database {db} already exists. Do you want to overwrite it? (yes/no): ").lower()
            if overwrite != 'yes':
                logger.info("Restore aborted.")
                if config.get('verbose'):
                    print("Restore aborted.")
                return
            overwrite = input("Are you sure you want to overwrite the existing database? This action cannot be undone. (yes/no): ").lower()
            if overwrite != 'yes':
                logger.info("Restore aborted.")
                if config.get('verbose'):
                    print("Restore aborted.")
                return
        else:
            subprocess.run(["mysql", "-u", user, f"--password={password}", "-e", f"CREATE DATABASE {db};"])

        with open(backup_path, 'rb') as file:
            decompress_process = subprocess.Popen(
                ["bunzip2"], stdin=file, stdout=subprocess.PIPE)
            restore_process = subprocess.Popen(
                ["mysql", "-u", user, f"--password={password}", db], stdin=decompress_process.stdout)

            decompress_process.stdout.close()
            restore_process.communicate()

        logger.info(f"{backup_path} restored to {db} database successfully.")
        if config.get('verbose'):
            print(f"{backup_path} restored to {db} database successfully.")

        if config.get('telegram_token') and config.get('telegram_chat_id'):
            send_telegram_message(config['telegram_token'], config['telegram_chat_id'], f"{backup_path} restored successfully to {db}.")
        if config.get('pushover_token') and config.get('pushover_user'):
            send_pushover_message(config['pushover_token'], config['pushover_user'], f"{backup_path} restored successfully to {db}.")
    except Exception as e:
        logger.error(f"Error restoring {db} database: {e}")
        if config.get('verbose') or config.get('debug'):
            print(f"Error restoring {db} database: {e}")
        if config.get('telegram_token') and config.get('telegram_chat_id'):
            send_telegram_message(config['telegram_token'], config['telegram_chat_id'], f"Error restoring {db} from {backup_path}: {e}")
        if config.get('pushover_token') and config.get('pushover_user'):
            send_pushover_message(config['pushover_token'], config['pushover_user'], f"Error restoring {db} from {backup_path}: {e}")


def main():
    if not Path(CONFIG_FILE).exists():
        logger.error(f"Configuration file {CONFIG_FILE} not found. Run the backup script with 'configure' argument to set up.")
        return

    with open(CONFIG_FILE, "r") as file:
        config = json.load(file)

    user, password = find_mariadb_credentials()
    if user is None or password is None:
        user = input("Enter MariaDB/MySQL username: ")
        password = input("Enter MariaDB/MySQL password: ")

    db = input("Enter the name of the database to restore: ")
    backup_path = input("Enter the path of the backup file: ")

    if config.get('debug'):
        logger.setLevel(logging.DEBUG)
    elif config.get('verbose'):
        logger.setLevel(logging.INFO)

    restore_backup(db, backup_path, user, password, config)


if __name__ == "__main__":
    main()
