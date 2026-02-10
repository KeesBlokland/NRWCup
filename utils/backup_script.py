import os
import shutil
import datetime

# BEGIN AI INSTRUCTIONS
# - Do not alter the directory structure.
# - Focus only on creating robust backups for the application.
# END AI INSTRUCTIONS

def create_backup(src_dir, backup_dir):
    """
    Create a ZIP backup of the specified source directory.

    Args:
        src_dir (str): The directory to back up.
        backup_dir (str): The directory to store backups.
    """
    try:
        # Check if the source directory exists
        if not os.path.exists(src_dir):
            print(f"Error: Source directory '{src_dir}' does not exist.")
            return

        # Create the backup directory if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Get the current date and time for the backup file name
        now = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_file = f'backup_{now}.zip'
        backup_path = os.path.join(backup_dir, backup_file)

        # Create the backup ZIP archive
        shutil.make_archive(os.path.splitext(backup_path)[0], 'zip', root_dir=src_dir)

        print(f"Backup created successfully: {backup_path}")
    except Exception as e:
        print(f"Error during backup: {e}")

if __name__ == "__main__":
    # Define the source and backup directories
    src_dir = 'app'  # Adjust this to the directory you want to back up
    backup_dir = 'backups'  # Directory to store backups

    create_backup(src_dir, backup_dir)
