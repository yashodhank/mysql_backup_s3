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
LOG_FILE = "backup.log"

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

def get_config_value(config, key, prompt):
    env_value = os.environ.get(key)
    if env_value is not None:
        return env_value
    return config.get(key, input(prompt) if prompt else None)

def configure_backup():
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {}
        
    user, password = find_mariadb_credentials()
    if user is None or password is None:
        user = get_config_value(config, 'DB_USER', 'Enter Database User: ')
        password = get_config_value(config, 'DB_PASSWORD', 'Enter Database Password: ')
    
    config['db_user'] = user
    config['db_password'] = password
    config['aws_access_key_id'] = get_config_value(config, 'AWS_ACCESS_KEY_ID', 'Enter AWS Access Key ID: ')
    config['aws_secret_access_key'] = get_config_value(config, 'AWS_SECRET_ACCESS_KEY', 'Enter AWS Secret Access Key: ')
    config['bucket_name'] = get_config_value(config, 'BUCKET_NAME', 'Enter S3 Bucket Name: ')
    config['region_name'] = get_config_value(config, 'REGION_NAME', 'Enter S3 Region Name: ')
    config['telegram_token'] = get_config_value(config, 'TELEGRAM_TOKEN', 'Enter Telegram Bot Token (optional, press enter to skip): ')
    config['telegram_chat_id'] = get_config_value(config, 'TELEGRAM_CHAT_ID', 'Enter Telegram Chat ID (optional, press enter to skip): ')
    config['pushover_token'] = get_config_value(config, 'PUSHOVER_TOKEN', 'Enter Pushover Application Token (optional, press enter to skip): ')
    config['pushover_user'] = get_config_value(config, 'PUSHOVER_USER', 'Enter Pushover User Key (optional, press enter to skip): ')
    config['verbose'] = get_config_value(config, 'VERBOSE', 'Enable verbose mode? (yes/no): ').lower() == 'yes'
    config['debug'] = get_config_value(config, 'DEBUG', 'Enable debug mode? (yes/no): ').lower() == 'yes'
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def send_telegram_message(token, chat_id, message, is_critical=False):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        if is_critical:
            data["disable_notification"] = False
        else:
            data["disable_notification"] = True
        requests.post(url, data=data)
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        if config.get('verbose') or config.get('debug'):
            print(f"Error sending Telegram message: {e}")

def send_pushover_message(token, user, message, is_critical=False):
    try:
        url = "https://api.pushover.net/1/messages.json"
        data = {
            "token": token,
            "user": user,
            "message": message,
            "sound": "magic" if is_critical else "pushover"
        }
        requests.post(url, data=data)
    except Exception as e:
        logger.error(f"Error sending Pushover message: {e}")
        if config.get('verbose') or config.get('debug'):
            print(f"Error sending Pushover message: {e}")

def backup_databases(config):
    user = config['db_user']
    password = config['db_password']
    hostname = socket.gethostname()
    ipv4 = socket.gethostbyname(hostname)

    s3 = boto3.client('s3',
                      aws_access_key_id=config['aws_access_key_id'],
                      aws_secret_access_key=config['aws_secret_access_key'],
                      region_name=config['region_name'])

    date_str = datetime.now().strftime('%d-%m-%Y')
    temp_dir = Path(f"/tmp/mysql_backup_s3/{date_str}")
    temp_dir.mkdir(parents=True, exist_ok=True)

    databases = subprocess.getoutput(f"mysql -u {user} -p{password} -e 'SHOW DATABASES;'").split('\n')[1:]
    for db in databases:
        backup_start_time = datetime.now()
        try:
            backup_file = temp_dir / f"{db}_backup_{backup_start_time.strftime('%Y%m%d%H%M%S')}.sql.bz2"
            with open(backup_file, 'wb') as file:
                dump_process = subprocess.Popen(["mysqldump", "-u", user, f"--password={password}", db], stdout=subprocess.PIPE)
                compress_process = subprocess.Popen(["bzip2"], stdin=dump_process.stdout, stdout=file)
                dump_process.stdout.close()  # Allow dump_process to receive a SIGPIPE if compress_process exits.
                compress_process.communicate()

            backup_end_time = datetime.now()
            duration = backup_end_time - backup_start_time

            backup_size = backup_file.stat().st_size
            uncompressed_size = subprocess.check_output(["bzip2", "-dc", backup_file, "|", "wc", "-c"], text=True).strip()

            with open(backup_file, 'rb') as file:
                object_name = f"{db}_backup_{backup_start_time.strftime('%Y%m%d%H%M%S')}.sql.bz2"
                s3.upload_fileobj(file, config['bucket_name'], object_name)

            stats_message = f"Database Name: {db}\n" \
                            f"Duration: {duration}\n" \
                            f"Type: full\n" \
                            f"Backup Finish Date: {backup_end_time.strftime('%d-%m-%Y %H:%M:%S')}\n" \
                            f"Backup Size: {uncompressed_size} bytes\n" \
                            f"Compressed Backup Size: {backup_size} bytes\n" \
                            f"Backup Start TimeDate: {backup_start_time.strftime('%d-%m-%Y %H:%M:%S')}\n" \
                            f"Backup End TimeDate: {backup_end_time.strftime('%d-%m-%Y %H:%M:%S')}\n" \
                            f"Server IPv4: {ipv4}\n" \
                            f"Server Hostname: {hostname}"

            logger.info(stats_message)
            if config.get('verbose'):
                print(stats_message)
            if config.get('telegram_token') and config.get('telegram_chat_id'):
                send_telegram_message(config['telegram_token'], config['telegram_chat_id'], stats_message)
            if config.get('pushover_token') and config.get('pushover_user'):
                send_pushover_message(config['pushover_token'], config['pushover_user'], stats_message)

        except Exception as e:
            error_message = f"Error backing up {db} database: {e}"
            logger.error(error_message)
            if config.get('verbose') or config.get('debug'):
                print(error_message)
            if config.get('telegram_token') and config.get('telegram_chat_id'):
                send_telegram_message(config['telegram_token'], config['telegram_chat_id'], error_message, is_critical=True)
            if config.get('pushover_token') and config.get('pushover_user'):
                send_pushover_message(config['pushover_token'], config['pushover_user'], error_message, is_critical=True)

    shutil.rmtree(temp_dir)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "configure":
        configure_backup()
    else:
        if not Path(CONFIG_FILE).exists():
            logger.error(f"Configuration file {CONFIG_FILE} not found. Run the script with 'configure' argument to set up.")
            return

        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)

        if config.get('debug'):
            logger.setLevel(logging.DEBUG)
        elif config.get('verbose'):
            logger.setLevel(logging.INFO)

        backup_databases(config)

if __name__ == "__main__":
    main()
