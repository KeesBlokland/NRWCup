"""
File: backup_script.py
Version: 1.2.0
Created: 2024-12-04
Last Updated: 2024-12-04
Description: Enhanced backup script for NRW Cup application
"""

import os
import shutil
import datetime
import zipfile
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def should_exclude(path):
    """
    Check if a path should be excluded from backup
    """
    exclude_patterns = {
        '__pycache__',
        '.pyc',
        '.pyo',
        '.pyd',
        '.git',
        '.zip',
        'venv',
        '.env',
        '.idea',
        '.vscode',
        'node_modules',
        '.pytest_cache',
        '.coverage',
        'backups',
        'utils',
        'doc_archives',
        'migrations',
        'routes/backups'
    }
    
    return any(pattern in path for pattern in exclude_patterns)

def create_backup(project_root, backup_dir):
    """
    Create a ZIP backup of the project directory.
    
    Args:
        project_root (str): Root directory of the project to back up
        backup_dir (str): Directory to store backups
    """
    try:
        # Resolve absolute paths
        project_root = os.path.abspath(project_root)
        backup_dir = os.path.abspath(backup_dir)
        
        logger.info(f"Starting backup from {project_root}")
        
        # Verify source directory exists
        if not os.path.exists(project_root):
            logger.error(f"Source directory '{project_root}' does not exist")
            return False
            
        # Create backup directory if needed
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_name = f'nrwcup_backup_{timestamp}.zip'
        backup_path = os.path.join(backup_dir, backup_name)
        
        # Create ZIP file
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Track total files for progress
            total_files = sum([len(files) for _, _, files in os.walk(project_root)])
            processed_files = 0
            
            # Walk through directory
            for root, dirs, files in os.walk(project_root):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if not should_exclude(d)]
                
                # Process each file
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Skip excluded files
                    if should_exclude(file_path):
                        continue
                        
                    # Calculate relative path for ZIP
                    rel_path = os.path.relpath(file_path, project_root)
                    
                    try:
                        # Add file to ZIP
                        zf.write(file_path, rel_path)
                        processed_files += 1
                        
                        # Log progress every 10 files
                        if processed_files % 10 == 0:
                            logger.info(f"Processed {processed_files}/{total_files} files")
                            
                    except Exception as e:
                        logger.error(f"Error adding {file_path}: {str(e)}")
        
        # Verify backup file was created and has content
        if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
            logger.info(f"Backup created successfully: {backup_path}")
            logger.info(f"Backup size: {os.path.getsize(backup_path) / (1024*1024):.2f} MB")
            return True
        else:
            logger.error("Backup file creation failed or file is empty")
            return False
            
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return False

def list_backups(backup_dir):
    """
    List all backups in the backup directory with size and date
    """
    try:
        backup_dir = os.path.abspath(backup_dir)
        if not os.path.exists(backup_dir):
            logger.error(f"Backup directory '{backup_dir}' does not exist")
            return
            
        backups = []
        for file in os.listdir(backup_dir):
            if file.startswith('nrwcup_backup_') and file.endswith('.zip'):
                path = os.path.join(backup_dir, file)
                size = os.path.getsize(path)
                created = datetime.datetime.fromtimestamp(os.path.getctime(path))
                backups.append({
                    'name': file,
                    'size': f"{size / (1024*1024):.2f} MB",
                    'created': created.strftime('%Y-%m-%d %H:%M:%S')
                })
                
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x['name'], reverse=True)
        
        if backups:
            logger.info("\nExisting backups:")
            for backup in backups:
                logger.info(f"{backup['name']} - {backup['size']} - {backup['created']}")
        else:
            logger.info("No backups found")
            
    except Exception as e:
        logger.error(f"Error listing backups: {str(e)}")

if __name__ == "__main__":
    # Get project root (parent directory of the script)
    project_root = str(Path(__file__).parent)
    backup_dir = os.path.join(project_root, 'backups')
    
    # Create backup
    if create_backup(project_root, backup_dir):
        # List existing backups
        list_backups(backup_dir)
