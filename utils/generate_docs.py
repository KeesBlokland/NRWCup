#!/usr/bin/env python3
"""
Generate a formatted document list from project files for AI conversations.
Includes database structure and sample data.
Maintains archived versions in doc_archives directory.
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
import shutil
import subprocess
import json


# BEGIN AI INSTRUCTIONS
# - Do not alter the database schema.
# - Use Flask=Appbuilder, and or Flask-admin and or Flask-WTF if it makes sense to do so.
# - No external links to CDN etc. allowed, standalone no internet app.
# - Respect the directory structure, 
# - Focus on enhancing usability or debugging issues only.
# - Use unique filenames, prefix with (shortened) directory name if required.
# - use logfiles for debugging where possible.
# - translate english user instuctions to German. (all oher text remains in english)
# - provide clear instructions where file snippets have to go. 
# END AI INSTRUCTIONS
# Load user exclusions from config file


def load_exclusions():
    """Load user-defined exclusions from config file"""
    config_file = Path('doc_config.json')
    default_exclusions = {
        'dirs': {
            '__pycache__',
            'venv',
            'env',
            '.git',
            '.idea',
            '.vscode',
            'instance',
            'node_modules',
            'migrations',
            'doc_archives',
            '__MACOSX'
        },
        'extensions': {
            '.pyc',
            '.pyo',
            '.pyd',
            '.log',
            '.pid',
            '.DS_Store',
            '.bak'
        },
        'files': {
            'bootstrap.min.css',
            'bootstrap.bundle.min.js',
            'jquery.min.js',
            'popper.min.js',
            'claude_documents_latest.txt',
            'generate_docs.py'
        }
    }
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                # Merge user exclusions with defaults
                exclusions = {
                    'dirs': set(default_exclusions['dirs']).union(set(user_config.get('dirs', []))),
                    'extensions': set(default_exclusions['extensions']).union(set(user_config.get('extensions', []))),
                    'files': set(default_exclusions['files']).union(set(user_config.get('files', [])))
                }
                return exclusions
        except json.JSONDecodeError:
            print("Warning: Invalid config file format. Using default exclusions.")
            return default_exclusions
    else:
        # Create default config file if it doesn't exist
        with open(config_file, 'w') as f:
            json.dump({
                'dirs': list(default_exclusions['dirs']),
                'extensions': list(default_exclusions['extensions']),
                'files': list(default_exclusions['files'])
            }, f, indent=4)
        print(f"Created default config file: {config_file}")
        return default_exclusions

def should_exclude(path):
    """Check if path should be excluded from documentation"""
    exclusions = load_exclusions()
    
    # Convert path to parts first
    path_str = str(path)
    path_parts = path_str.split(os.sep)
    
    # Check directories
    if any(part in exclusions['dirs'] for part in path_parts):
        return True
    
    # Check minified files
    if path.suffix in {'.css', '.js'} and '.min.' in path.name:
        return True
    
    # Check extensions and filenames
    return (path.suffix in exclusions['extensions'] or
            path.name in exclusions['files'])

def extract_db_info(db_path):
    """Extract database structure and sample data"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        output = ["-- Database Structure and Sample Data --\n"]
        
        for table in tables:
            table_name = table[0]
            # Skip SQLite internal tables
            if table_name.startswith('sqlite_'):
                continue
                
            # Get table structure
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            output.append(f"\n-- Table: {table_name}")
            output.append("CREATE TABLE IF NOT EXISTS {} (".format(table_name))
            column_defs = []
            for col in columns:
                column_defs.append(f"    {col[1]} {col[2]}" + 
                                 (" PRIMARY KEY" if col[5] == 1 else "") +
                                 (" NOT NULL" if col[3] == 1 else ""))
            output.append(",\n".join(column_defs))
            output.append(");")
            
            # Get sample data (first 5 rows)
            try:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
                rows = cursor.fetchall()
                if rows:
                    output.append(f"\n-- Sample data for {table_name}")
                    for row in rows:
                        output.append(f"INSERT INTO {table_name} VALUES {str(row)};")
            except sqlite3.Error as e:
                output.append(f"-- Error getting sample data: {e}")
            
            output.append("\n")
            
        conn.close()
        return "\n".join(output)
    except sqlite3.Error as e:
        return f"Error extracting database info: {e}"

def should_exclude(path):
    """Check if path should be excluded from documentation"""
    exclude_dirs = {
        '__pycache__',
        'venv',
        'env',
        '.git',
        '.idea',
        '.vscode',
        'instance',
        'node_modules',
        'migrations',
        'doc_archives',
        '__MACOSX'
    }
    exclude_extensions = {
        '.pyc',
        '.pyo',
        '.pyd',
        '.log',
        '.pid',
        '.DS_Store',
        '.bak'
    }
    
    exclude_files = {
        'bootstrap.min.css',
        'bootstrap.bundle.min.js',
        'jquery.min.js',
        'popper.min.js',
        'claude_documents_latest.txt',
        'generate_docs.py'
    }
    
    # Convert path to parts first
    path_str = str(path)
    path_parts = path_str.split(os.sep)
    
    # Check directories
    if any(part in exclude_dirs for part in path_parts):
        return True
    
    # Check minified files
    if path.suffix in {'.css', '.js'} and '.min.' in path.name:
        return True
    
    # Check extensions and filenames
    return (path.suffix in exclude_extensions or
            path.name in exclude_files)

def get_directory_tree():
    """Generate a directory tree with depth 3."""
    try:
        tree_output = subprocess.check_output(['tree', '-L', '3'], text=True)
        return tree_output
    except FileNotFoundError:
        return "Error: The 'tree' command is not available. Please install it using your package manager."

def get_user_remarks(latest_file):
    """Prompt user for remarks to include and preserve previous remarks"""
    previous_remarks = ""

    # Check if the latest file exists and extract previous remarks
    if Path(latest_file).exists():
        with open(latest_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "<remarks>" in content and "</remarks>" in content:
                previous_remarks = content.split("<remarks>")[1].split("</remarks>")[0].strip()

    # Display previous remarks
    if previous_remarks:
        print("\n--- Previous Remarks ---")
        print(previous_remarks)
        print("------------------------")

    # Prompt for new remarks
    print("\nEnter new remarks to include (press Enter to skip):")
    print("Example: What the app does, known issues, pending tasks, etc.")
    print("-" * 50)
    remarks = []
    while True:
        line = input("> ")
        if not line.strip():
            break
        remarks.append(line)

    # Add timestamp to new remarks
    if remarks:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        remarks = [f"[{timestamp}] {line}" for line in remarks]
        return f"{previous_remarks}\n\n" + "\n".join(remarks) if previous_remarks else "\n".join(remarks)

    # Return previous remarks if no new remarks are added
    return previous_remarks


def generate_documents():
    """Walk through project and generate formatted document entries"""
    project_root = Path('.')
    documents = []
    index = 1

    # First, process regular files
    for path in sorted(project_root.rglob('*')):
        if path.is_file() and not should_exclude(path):
            try:
                # Skip databases for now, we'll handle them separately
                if path.suffix in {'.db', '.sqlite', '.sqlite3'}:
                    continue
                    
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                source_path = str(path).replace('\\', '/')
                if source_path.startswith('./'):
                    source_path = source_path[2:]
                
                doc = f"""<document index="{index}">
<source>{source_path}</source>
<document_content>{content}</document_content>
</document>"""
                documents.append(doc)
                print(f"Added: {source_path}")
                index += 1
            except Exception as e:
                print(f"Error processing {path}: {e}", file=sys.stderr)

    # Then handle databases
    for path in project_root.rglob('*'):
        if path.is_file() and path.suffix in {'.db', '.sqlite', '.sqlite3'}:
            try:
                db_content = extract_db_info(str(path))
                source_path = str(path).replace('\\', '/')
                if source_path.startswith('./'):
                    source_path = source_path[2:]
                
                doc = f"""<document index="{index}">
<source>{source_path} (Structure and Sample Data)</source>
<document_content>
{db_content}
</document_content>
</document>"""
                documents.append(doc)
                print(f"Added database info: {source_path}")
                index += 1
            except Exception as e:
                print(f"Error processing database {path}: {e}", file=sys.stderr)

    return documents

def main():
    """Generate and save the document list"""
    try:
        print("Starting document generation...")

        # Path to the latest file
        latest_file = 'claude_documents_latest.txt'

        # Generate directory tree
        dir_tree = get_directory_tree()

        # Prompt for user remarks, preserving existing remarks
        remarks = get_user_remarks(latest_file)

        documents = generate_documents()
        output = "<documents>\n"
        output += "<directory_tree>\n" + dir_tree + "\n</directory_tree>\n"
        if remarks:
            output += f"<remarks>\n{remarks}\n</remarks>\n"
        output += "\n".join(documents) + "\n</documents>"
        
        # Create archives directory if it doesn't exist
        archive_dir = Path('doc_archives')
        archive_dir.mkdir(exist_ok=True)
        
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f'claude_documents_{timestamp}.txt'
        archive_path = archive_dir / output_file
        
        # Also create a 'latest' version in project root
        # Write to both locations
        with open(archive_path, 'w', encoding='utf-8') as f:
            f.write(output)
        
        # Copy to latest
        shutil.copy2(archive_path, latest_file)
        
        # Keep only the last 10 archived versions
        archived_files = sorted(archive_dir.glob('claude_documents_*.txt'))
        if len(archived_files) > 10:
            for old_file in archived_files[:-10]:
                old_file.unlink()
            print(f"\nCleaned up old archives, keeping latest 10 versions.")
        
        print(f"\nSuccessfully processed {len(documents)} files.")
        print(f"Output saved to:")
        print(f"  - Archive: {archive_path}")
        print(f"  - Latest: {latest_file}")
        
        file_size = os.path.getsize(archive_path) / 1024  # Convert to KB
        print(f"Output file size: {file_size:.1f} KB")
        print("\nYou can now copy the contents of 'claude_documents_latest.txt' into your conversation with Claude.")
        
        # List all available archives
        print("\nAvailable archives:")
        for archive in sorted(archive_dir.glob('claude_documents_*.txt'), reverse=True):
            archive_size = os.path.getsize(archive) / 1024
            print(f"  - {archive.name} ({archive_size:.1f} KB)")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
