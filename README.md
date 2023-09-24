# MySQL Backup/Restore to/from S3 - mysql_backup_s3

This project allows for the automated backup of MySQL databases to an S3 bucket and restoration of those backups. It is configured to run as a service to ensure regular backups without manual intervention.

## Prerequisites
- Python 3.x
- MariaDB or MySQL Server
- A Wasabi or AWS S3 Bucket
- An environment to run the service (e.g., a server where the database is hosted)

## Installation and Setup

1. **Clone the Repository**
   ```sh
   git clone https://github.com/yashodhank/mysql_backup_s3
   cd mysql_backup_s3
   ```

2. **Create a Virtual Environment and Activate It**
   ```sh
   python3 -m venv venv-mysql_backup_s3
   source venv-mysql_backup_s3/bin/activate
   ```

3. **Install Required Packages**
   ```sh
   pip3 install -r requirements.txt
   ```

4. **Secure Sensitive Information**

   To secure sensitive information like database passwords and API keys, it is recommended to use environment variables. This is a good practice to avoid exposing sensitive information. Set the following environment variables in your shell, or better, in your `.bashrc` or `.bash_profile` file. After setting them, restart your terminal session so that the changes take effect. If environment variables are not set, when `backup.py configure` is invoked, these details will be prompted and stored in `backup_config.json` in the same directory, which is less secure.
   ```sh
   export DB_USER='mariadb_user'
   export DB_PASSWORD='mariadb_password'
   export AWS_ACCESS_KEY_ID='AKIAIOSFODNN7EXAMPLE'
   export AWS_SECRET_ACCESS_KEY='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
   ```

5. **Configure the Backup Script**

   Run the configuration wizard to set up the backup script:
   ```sh
   python3 backup.py configure
   ```

   Follow the prompts to configure the S3 bucket name, region name, and enable verbose or debug mode if needed. If the environment variables for sensitive information are not set, they will be prompted during this step. If the required database user and password are not found in standard locations, they will also be prompted.
   ```sh
   Enter AWS Access Key ID [AKIAIOSFODNN7EXAMPLE]: 
   Enter AWS Secret Access Key [wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY]: 
   Enter S3 Bucket Name: mydatabase-backups
   Enter S3 Region Name [us-east-1]: 
   Enter Database User [mariadb_user]: 
   Enter Database Password [mariadb_password]: 
   Enter Telegram Bot Token (optional, press enter to skip): 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   Enter Telegram Chat ID (optional, press enter to skip): 123456789
   Enter Pushover Application Token (optional, press enter to skip): azGDORePK8gMaC0QOYAMyEEuzJnyUi
   Enter Pushover User Key (optional, press enter to skip): uQiRzpo4DXghDmr9QzzfQu27cmVRsG
   Enable verbose mode? (yes/no): yes
   Enable debug mode? (yes/no): no
   ```

   If you skip the optional fields, you won't receive notifications via Telegram or Pushover. If you enable verbose or debug mode, more detailed information will be printed to the console and log file during backup operations.

6. **Create a Systemd Service File**

   Create a systemd service file to run the backup script as a service:
   ```sh
   sudo nano /etc/systemd/system/mysql_backup_s3.service
   ```

   Add the following content to the service file, replacing `/path/to/mysql_backup_s3` with the actual path to your `mysql_backup_s3` directory:
   ```ini
   [Unit]
   Description=MySQL Backup to S3
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/path/to/mysql_backup_s3
   Environment="PATH=/path/to/mysql_backup_s3/venv-mysql_backup_s3/bin"
   ExecStart=/path/to/mysql_backup_s3/venv-mysql_backup_s3/bin/python3 /path/to/mysql_backup_s3/backup.py
   Restart=on-failure
   RestartSec=30s

   [Install]
   WantedBy=default.target
   ```

7. **Start and Enable the Service**
   ```sh
   sudo systemctl start mysql_backup_s3.service
   sudo systemctl enable mysql_backup_s3.service
   ```

   This will start the service and ensure it starts on boot.

## Usage

### Backup
Once the service is started, it will automatically back up your databases to the configured S3 bucket at regular intervals without any manual intervention.

### Restore

To restore a database, use the `restore.py` script:

1. **Activate the Virtual Environment**
   ```sh
   source venv-mysql_backup_s3/bin/activate
   ```

2. **Run the Restore Script**
   ```sh
   python3 restore.py
   ```

   Follow the prompts to restore a specific backup from the S3 bucket to the local MySQL/MariaDB server.

    If the script can locate MySQL/MariaDB credentials from standard or control panel-specific locations, it will use them.
    If not, it will prompt you to enter the database user and password.
    Enter the name of the database to restore and the path of the backup file.
    If the database already exists, it will ask for confirmation twice before overwriting it.

## Notifications

- **Telegram Notifications:**
  - The script can send Telegram notifications for successful backups/restores and critical errors.
  - Configure the `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` during the configuration step or set them as environment variables.

- **Pushover Notifications:**
  - The script can send Pushover notifications for successful backups/restores and critical errors.
  - Configure the `PUSHOVER_TOKEN` and `PUSHOVER_USER` during the configuration step or set them as environment variables.

## Logging

- The script logs all events to `backup.log` and `restore.log` in the script's directory.
- You can monitor these log files for any issues or to verify successful backups/restores.
- Secure the log files and avoid logging sensitive information.

## Example

### Backup
For example, if you have a database named `mydatabase` and you have configured the S3 bucket as `mybucket`, the backup script will automatically back up the `mydatabase` database to the `mybucket` S3 bucket.

### Restore
For instance, to restore the `mydatabase` database from a backup file named `mydatabase_backup_20230924.sql.bz2` located in the `mybucket` S3 bucket, run the restore script and enter the database name as `mydatabase` and the backup file 
path as `mydatabase_backup_20230924.sql.bz2`.

## Security

- Secure the configuration file and environment variables containing sensitive information, such as passwords and API keys.
- Regularly monitor the log files and set up log rotation to avoid filling up the disk space.
- Set up an alerting system to notify you if the script encounters any errors.

## Contributing
Feel free to fork the project, create a feature branch, and open a Pull Request. For bugs, please open an issue.

## License
This project is open-source and available under the MIT License.


### Notes:
> - The above README assumes that the user has basic knowledge of using the command line, Python, and MariaDB/MySQL.
> - The README provides a basic outline. You might want to customize and enhance it according to your project’s specific needs, adding more details, sections, or clarifications as necessary.
> - Make sure to test all the instructions provided in the README to ensure they are accurate and clear before publishing it.
