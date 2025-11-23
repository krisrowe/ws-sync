import click
import os
import sys
import fnmatch # For glob-style pattern matching
import hashlib # For file content hashing
import glob # For glob pattern matching
import yaml # For YAML parsing/dumping
import json # For parsing gcloud output
import subprocess
from datetime import datetime # For handling timestamps
from devws_cli.utils import _run_command, _load_global_config, GLOBAL_DEVWS_CONFIG_FILE, get_git_repo_info, get_gcs_profile_config
from devws_cli.gcs_manager import GCSManager # Import the new GCSManager
from devws_cli.gcs_profile_manager import GCSProfileManager # Import the new GCSProfileManager

# from devws_cli.managers.locals_manager import LocalsManager # Removed LocalsManager as it will be refactored

WS_SYNC_FILE = ".ws-sync"

def _get_local_repo_path():
    """
    Determines the local repository path, respecting PROJ_LOCAL_CONFIG_SYNC_PATH.
    """
    return os.environ.get("PROJ_LOCAL_CONFIG_SYNC_PATH", os.getcwd())

def _get_ws_sync_path():
    """
    Returns the full path to the .ws-sync file, respecting PROJ_LOCAL_CONFIG_SYNC_PATH.
    """
    return os.path.join(_get_local_repo_path(), WS_SYNC_FILE)

def _get_managed_files():
    """
    Reads the .ws-sync file and returns a list of file patterns.
    """
    ws_sync_path = _get_ws_sync_path()
    if not os.path.exists(ws_sync_path):
        click.echo(f"❌ '{WS_SYNC_FILE}' not found in the current directory ({_get_local_repo_path()}). Run 'devws local init' first.", err=True)
        sys.exit(1)

    managed_files = []
    with open(ws_sync_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                managed_files.append(line)
    return managed_files

def _get_gitignore_patterns():
    """
    Reads .gitignore and returns a list of patterns.
    """
    gitignore_path = os.path.join(_get_local_repo_path(), ".gitignore")
    if not os.path.exists(gitignore_path):
        return []

    patterns = []
    with open(gitignore_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns

def _is_ignored(file_path, gitignore_patterns):
    """
    Checks if a file path matches any .gitignore pattern.
    """
    for pattern in gitignore_patterns:
        # Handle exact matches and glob patterns
        if fnmatch.fnmatch(file_path, pattern):
            return True
        # Handle directory patterns (e.g., 'node_modules/')
        # If pattern ends with '/', it matches directories.
        # We need to check if file_path is exactly that directory, or a file/directory within it.
        if pattern.endswith('/'):
            # Check if file_path is the directory itself (without trailing slash)
            if file_path == pattern.rstrip('/'):
                return True
            # Check if file_path is inside the directory
            if file_path.startswith(pattern):
                return True
        # Handle patterns that match directories themselves (e.g., 'venv')
        if os.path.isdir(file_path) and fnmatch.fnmatch(os.path.basename(file_path), pattern):
            return True
    return False

def _get_file_hash(file_path, algorithm='md5'):
    """Calculates the hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use ('md5' or 'sha256')
    
    Returns:
        Base64-encoded hash for MD5 (to match GCS format), hex for SHA256
    """
    if not os.path.exists(file_path):
        return None
    
    if algorithm == 'md5':
        hasher = hashlib.md5()
    else:
        hasher = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            hasher.update(chunk)
    
    # Return base64-encoded hash for MD5 to match GCS format
    if algorithm == 'md5':
        import base64
        return base64.b64encode(hasher.digest()).decode('utf-8')
    else:
        return hasher.hexdigest()


def _get_gcs_file_status(gcs_manager, gcs_object_path):
    """
    Determines the existence, type (file/directory), and relevant metadata
    of a given path in Google Cloud Storage using the GCSManager.

    Args:
        gcs_manager (GCSManager): An instance of the GCSManager.
        gcs_object_path (str): The full gs:// path to the GCS object or prefix.

    Returns:
        dict: A dictionary with 'status', 'type', and 'metadata'.
              metadata includes 'last_modified_timestamp' (ISO format) and 'md5_hash'.
    """
    status = "Not Present"
    file_type = "N/A"
    metadata = {}

    # First, try to see if it's a directory (prefix) by listing contents
    # Use gcs_ls with recursive to check for contents under the path
    try:
        # Check if it's a directory by listing its content. If it has content, it's a directory.
        # Use a more specific check, like 'gsutil ls gs://bucket/path/'
        # Note: gcs_ls needs to be robust for directories too.
        # For now, if gcs_ls returns anything, we assume it's a directory or has contents.
        # A more precise check would be to check for gs://path/ and gs://path/*
        if gcs_object_path.endswith('/'): # If it's explicitly a directory path
            list_output = gcs_manager.gcs_ls(gcs_object_path, recursive=False)
            if list_output: # If it's a directory with contents
                 return {
                    "status": "Present",
                    "type": "Directory",
                    "metadata": {}
                }
            else: # Check if the directory itself exists
                try:
                    gcs_manager.gcs_stat(gcs_object_path)
                    return {
                        "status": "Present",
                        "type": "Directory",
                        "metadata": {}
                    }
                except subprocess.CalledProcessError:
                    pass # Not an explicit directory object
        else: # Try listing as a prefix
            list_output = gcs_manager.gcs_ls(f"{gcs_object_path}/", recursive=False)
            if list_output:
                # Verify if it's actually a directory.
                # gsutil ls -d path/ might return path (the file) if it exists.
                # A true directory should return path/ (with trailing slash) or have multiple items.
                is_directory = False
                for item in list_output:
                    if item.endswith('/') or len(list_output) > 1:
                        is_directory = True
                        break
                
                if is_directory:
                    return {
                        "status": "Present",
                        "type": "Directory",
                        "metadata": {}
                    }

    except Exception: # GCSManager.gcs_ls might raise if gsutil not found etc.
        pass # Not a directory, or empty directory, proceed to check if it's a file

    # If not identified as a directory, try to get file metadata using gcloud storage via GCSManager.gcs_stat
    try:
        obj_stats = gcs_manager.gcs_stat(gcs_object_path)
        if obj_stats:
            status = "Present"
            file_type = "File" # If stat worked, it's a file

            # Extract metadata from stats (md5_hash is at top level)
            if 'Update time' in obj_stats: # Key from gsutil stat -L
                metadata['last_modified_timestamp'] = obj_stats['Update time']
            if 'Hash (md5)' in obj_stats: # Key from gsutil stat -L (base64-encoded)
                metadata['md5_hash'] = obj_stats['Hash (md5)']

            return {
                "status": status,
                "type": file_type,
                "metadata": metadata
            }
    except Exception as e: # GCSManager.gcs_stat will raise CalledProcessError if not found
        click.echo(f"DEBUG: gcs_stat failed for {gcs_object_path}: {e}", err=True)
        pass # If both directory check and file check failed, then it's not present.

    return {
        "status": "Not Present",
        "type": "N/A",
        "metadata": {}
    }


def _get_local_file_status(local_file_path):
    """
    Determines the existence, type (file/directory), and relevant metadata
    of a given path on the local filesystem.

    Args:
        local_file_path (str): The full path to the local file or directory.

    Returns:
        dict: A dictionary with 'status', 'type', and 'metadata'.
              metadata includes 'last_modified_timestamp' (ISO format) and 'sha256_hash'.
    """
    status = "Not Present"
    file_type = "N/A"
    metadata = {}

    if os.path.exists(local_file_path):
        status = "Present"
        if os.path.isdir(local_file_path):
            file_type = "Directory"
        elif os.path.isfile(local_file_path):
            file_type = "File"
            try:
                # Get last modified timestamp
                mtime = os.path.getmtime(local_file_path)
                metadata['last_modified_timestamp'] = datetime.fromtimestamp(mtime).isoformat()
                # Get MD5 hash for files (base64-encoded to match GCS format)
                metadata['md5_hash'] = _get_file_hash(local_file_path, algorithm='md5')
            except Exception as e:
                click.echo(f"❌ Error getting local file metadata for {local_file_path}: {e}", err=True)
                # Continue without metadata if error occurs
        
    return {
        "status": status,
        "type": file_type,
        "metadata": metadata
    }

def _generate_ascii_table(data):
    """
    Generates a human-readable ASCII table from a list of dictionaries.

    Args:
        data (list[dict]): A list of dictionaries, where each dictionary represents a row.
                           All dictionaries are expected to have the same keys.

    Returns:
        str: The ASCII table as a string.
    """
    if not data:
        return "No data to display."

    # Get columns from the first row
    columns = [(key, key.replace('_', ' ').title()) for key in data[0].keys()]
    
    # Calculate column widths
    column_widths = {}
    for col_key, col_header in columns:
        # Start with header width
        column_widths[col_key] = len(col_header)
        # Check all data rows
        for row in data:
            value_len = len(str(row.get(col_key, '')))
            if value_len > column_widths[col_key]:
                column_widths[col_key] = value_len
    
    # Build the header row
    headers = [col_header for _, col_header in columns]
    header_line = " | ".join(headers[i].ljust(column_widths[columns[i][0]]) for i in range(len(columns)))
    
    # Build the separator line
    separator_line = "-+-".join("-" * column_widths[col_key] for col_key, _ in columns)

    table_rows = [header_line, separator_line]

    # Build data rows
    for row in data:
        row_values = []
        for key, _ in columns:
            row_values.append(str(row.get(key, '')).ljust(column_widths[key]))
        table_rows.append(" | ".join(row_values))

    return "\n".join(table_rows)


@click.group()
def local():
    """
    Manages project-specific configuration files.

    This set of commands allows you to synchronize project-specific,
    non-version-controlled files (like .env or local configs)
    across different workstations using a GCS backend.
    """
    pass

@local.command()
def init():
    """
    Initializes a .ws-sync file in the current Git repository.
    This file defines which project-specific files are managed by 'devws local'.
    """
    global_config, _ = _load_global_config()
    profile_name = global_config.get('default_gcs_profile', 'default')
    
    project_id, bucket_name = get_gcs_profile_config(profile_name)
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile_name}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)

    gcs_manager = GCSManager(bucket_name, profile_name=profile_name) # Instantiate GCSManager

    # Check if inside a Git repository
    owner, repo_name = get_git_repo_info()
    if not owner or not repo_name:
        click.echo("❌ Not inside a Git repository. 'devws local init' must be run from a Git repository root.", err=True)
        sys.exit(1)

    ws_sync_path = _get_ws_sync_path()

    if os.path.exists(ws_sync_path):
        click.echo(f"⚠️ '{WS_SYNC_FILE}' already exists in this repository.", err=True)
        if not click.confirm("Do you want to overwrite it?"):
            click.echo("Operation cancelled.")
            sys.exit(0)

    click.echo(f"DEBUG: global_config in init: {global_config}")
    candidate_glob_patterns = global_config.get('local_sync_candidates', [])
    click.echo(f"DEBUG: candidate_glob_patterns in init: {candidate_glob_patterns}")
    gitignore_patterns = _get_gitignore_patterns()
    
    auto_added_files = []
    initial_ws_sync_content = []

    # Scan for candidate files that exist and are gitignored
    for pattern in candidate_glob_patterns:
        # Iterate through all files in the local repo path, including dotfiles
        for file_name in os.listdir(_get_local_repo_path()):
            file_path_in_repo = os.path.join(_get_local_repo_path(), file_name)
            if fnmatch.fnmatch(file_name, pattern):
                if os.path.isfile(file_path_in_repo):
                    if _is_ignored(file_name, gitignore_patterns): # Pass file_name for gitignore check
                        if file_name not in initial_ws_sync_content: # Avoid duplicates
                            initial_ws_sync_content.append(file_name)
                            auto_added_files.append(file_name)

    default_content = f"""# This file specifies project-specific files that should be synchronized
# across workstations for the same developer/user via the 'devws local' utility.
#
# IMPORTANT: All files listed here should also be included in your project's .gitignore
# to prevent accidental version control of sensitive or local-only configurations.
#
# Example:
# .env
# my-local-config.json
#
"""
    # Add auto-added files to the default content
    if auto_added_files:
        default_content += "\n# Automatically added based on global config and .gitignore:\n"
        for f in initial_ws_sync_content:
            default_content += f"{f}\n"

    try:
        with open(ws_sync_path, 'w') as f:
            f.write(default_content)
        click.echo(f"✅ Created '{WS_SYNC_FILE}' in the current repository ({_get_local_repo_path()}).")
        if auto_added_files:
            click.echo("The following files were automatically added to .ws-sync:")
            for f in auto_added_files:
                click.echo(f"  - {f}")
        click.echo("Please edit this file to list the project-specific files you want to manage.")
    except IOError as e:
        click.echo(f"❌ Error creating '{WS_SYNC_FILE}': {e}", err=True)
        sys.exit(1)


def _get_dry_run_results(gcs_manager, managed_files, base_gcs_path, gitignore_patterns, local_repo_path, force):
    """
    Generates dry run results for the pull command.
    """
    dry_run_results = []

    for file_pattern in managed_files:
        local_file_path = os.path.join(local_repo_path, file_pattern)
        gcs_object_path = f"{base_gcs_path}/{file_pattern}"
        
        # Get local and GCS file status
        local_file_status = _get_local_file_status(local_file_path)
        gcs_file_status = _get_gcs_file_status(gcs_manager, gcs_object_path)

        # Determine actual local status string for display
        local_status_str = local_file_status['status']
        if local_file_status['status'] == "Present" and local_file_status['type'] == "File":
            if gcs_file_status['status'] == "Present" and gcs_file_status['type'] == "File":
                # Compare MD5 hashes for content difference
                local_hash = local_file_status['metadata'].get('md5_hash')
                gcs_hash = gcs_file_status['metadata'].get('md5_hash')
                
                if local_hash and gcs_hash:
                    if local_hash == gcs_hash:
                        local_status_str = "Present (Same)"
                    else:
                        local_status_str = "Present (Different)"
                else:
                    # If we can't get hashes, assume different to be safe
                    local_status_str = "Present (Different)"
            else:
                local_status_str = "Present"
        elif local_file_status['status'] == "Present" and local_file_status['type'] == "Directory":
            local_status_str = "Present (Dir)"


        # Determine Action
        action = "None"
        ignored_by_gitignore = "Yes" if _is_ignored(file_pattern, gitignore_patterns) else "No"
        
        if ignored_by_gitignore == "Yes":
            action = "Skip (Ignored)"
        elif gcs_file_status['status'] == "Present" and gcs_file_status['type'] == "File":
            if local_file_status['status'] == "Present" and local_file_status['type'] == "File":
                # If both exist and are files, and force is not used, skip.
                # If force is used, it would overwrite.
                if force:
                    action = "Overwrite"
                else:
                    action = "Skip (Local Exists)"
            elif local_file_status['status'] == "Present" and local_file_status['type'] == "Directory":
                action = "Conflict (GCS file, local dir)"
            else: # Local not present or not a file
                action = "Pull"
        elif gcs_file_status['status'] == "Present" and gcs_file_status['type'] == "Directory":
            if local_file_status['status'] == "Present" and local_file_status['type'] == "File":
                action = "Conflict (GCS dir, local file)"
            else:
                action = "Sync Directory" # Indicates that contents under this prefix would be synced.
        else: # GCS Not Present or Unknown Error
            if local_file_status['status'] == "Present":
                action = "No GCS counterpart"
            else:
                action = "Neither exists"

        dry_run_results.append({
            "file_pattern": file_pattern,
            "local_status": local_status_str,
            "gcs_status": gcs_file_status['status'],
            "ignored_by_gitignore": ignored_by_gitignore,
            "action": action
        })
    
    return dry_run_results

@local.command()
@click.option('--force', is_flag=True, help='Overwrite local changes if conflicts exist.')
@click.option('--dry-run', is_flag=True, help='Perform a dry run without actually pulling files, showing what would happen.')
@click.option('--json', 'json_output', is_flag=True, help='Output dry run results as JSON.')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def pull(force, dry_run, json_output, debug):
    """
    Pulls all files listed in .ws-sync from GCS to the local project directory.
    """
    # Use LocalsManager for silent/debug context, but GCS operations via GCSManager
    # locals_manager = LocalsManager(silent=json_output, debug=debug) # LocalsManager no longer needed for GCS ops
    owner, repo_name = get_git_repo_info()
    if not owner or not repo_name:
        sys.exit(1)

    profile_name = _load_global_config()[0].get('default_gcs_profile', 'default')
    project_id, bucket_name = get_gcs_profile_config(profile_name)
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile_name)

    managed_files = _get_managed_files()
    if not managed_files:
        click.echo(f"ℹ️ No files listed in '{WS_SYNC_FILE}'. Nothing to pull.")
        sys.exit(0)

    base_gcs_path = gcs_manager.get_repo_gcs_path()
    if not base_gcs_path:
        click.echo(f"❌ Could not determine GCS path for repository.", err=True)
        sys.exit(1)
    
    if dry_run:
        if not json_output: # Only echo if not JSON output
            click.echo(f"ℹ️ Performing dry run for project '{owner}/{repo_name}' from GCS bucket '{gcs_manager.bucket_url}'...")
        
        gitignore_patterns = _get_gitignore_patterns()
        local_repo_path = _get_local_repo_path()

        dry_run_results = _get_dry_run_results(
            gcs_manager=gcs_manager, # Pass gcs_manager
            managed_files=managed_files,
            base_gcs_path=base_gcs_path,
            gitignore_patterns=gitignore_patterns,
            local_repo_path=local_repo_path,
            force=force
        )
        
        if json_output:
            print(json.dumps(dry_run_results, indent=2))
        else:
            click.echo(_generate_ascii_table(dry_run_results))
        
        return # Exit after dry run

    # Original pull logic (only if not dry_run)
    click.echo(f"ℹ️ Pulling files for project '{owner}/{repo_name}' from GCS bucket '{gcs_manager.bucket_url}'...")
    
    # Track results for summary table
    pull_results = []
    gitignore_patterns = _get_gitignore_patterns()

    local_repo_path = _get_local_repo_path()

    for file_pattern in managed_files:
        local_file_path = os.path.join(local_repo_path, file_pattern)
        gcs_object_path = f"{base_gcs_path}/{file_pattern}"
        
        action_taken = "Unknown"
        status = "Unknown"

        # Check if local file exists and if we should skip it
        if os.path.exists(local_file_path) and not force:
            # Skip force check for directories - always sync them
            if os.path.isdir(local_file_path):
                # Directories are synced recursively, proceed with pull
                pass
            else:
                # For files, check if it's the same as GCS version
                local_file_status = _get_local_file_status(local_file_path)
                gcs_file_status = _get_gcs_file_status(gcs_manager, gcs_object_path) # Pass gcs_manager
                
                # Skip the warning if files have identical content (same MD5 hash)
                if (local_file_status.get('type') == 'File' and 
                    gcs_file_status.get('type') == 'File' and
                    local_file_status.get('metadata', {}).get('md5_hash') == 
                    gcs_file_status.get('metadata', {}).get('md5_hash')):
                    # Files are identical, skip silently
                    click.echo(f"✅ '{local_file_path}' is already up to date.")
                    action_taken = "Skipped (Up to date)"
                    status = "✅"
                    pull_results.append({
                        "file_pattern": file_pattern,
                        "action": action_taken,
                        "status": status
                    })
                    continue
                
                # Files are different, show warning
                click.echo(f"⚠️ Local file '{local_file_path}' already exists. Use --force to overwrite.")
                action_taken = "Skipped (Exists)"
                status = "⚠️"
                pull_results.append({
                    "file_pattern": file_pattern,
                    "action": action_taken,
                    "status": status
                })
                continue
        
        click.echo(f"⬇️ Pulling '{gcs_object_path}' to '{local_file_path}'...")
        if gcs_manager.gcs_cp(gcs_object_path, local_file_path, recursive=True, debug=debug): # Use gcs_manager.gcs_cp
            click.echo(f"✅ Pulled '{local_file_path}'.")
            action_taken = "Pulled"
            status = "✅"
        else:
            click.echo(f"❌ Failed to pull '{local_file_path}'.", err=True)
            action_taken = "Failed"
            status = "❌"
        
        pull_results.append({
            "file_pattern": file_pattern,
            "action": action_taken,
            "status": status
        })
    
    # Display summary table
    if pull_results:
        click.echo("\n📊 Pull Summary:")
        # Format results for display
        summary_data = []
        for result in pull_results:
            summary_data.append({
                "File": result["file_pattern"],
                "Status": result["status"],
                "Action": result["action"]
            })
        click.echo(_generate_ascii_table(summary_data))

@local.command()
@click.option('--force', is_flag=True, help='Overwrite GCS version if conflicts exist.')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def push(force, debug):
    """
    Pushes all files listed in .ws-sync from the local project directory to GCS.
    """
    owner, repo_name = get_git_repo_info()
    if not owner or not repo_name:
        sys.exit(1)

    profile_name = _load_global_config()[0].get('default_gcs_profile', 'default')
    project_id, bucket_name = get_gcs_profile_config(profile_name)
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile_name)
    
    managed_files = _get_managed_files()
    if not managed_files:
        click.echo(f"ℹ️ No files listed in '{WS_SYNC_FILE}'. Nothing to push.")
        sys.exit(0)

    base_gcs_path = gcs_manager.get_repo_gcs_path()
    if not base_gcs_path:
        click.echo(f"❌ Could not determine GCS path for repository.", err=True)
        sys.exit(1)

    click.echo(f"ℹ️ Pushing files for project '{owner}/{repo_name}' to GCS bucket '{gcs_manager.bucket_url}'...")

    gitignore_patterns = _get_gitignore_patterns()
    local_repo_path = _get_local_repo_path()

    for file_pattern in managed_files:
        local_file_path = os.path.join(local_repo_path, file_pattern)
        gcs_object_path = f"{base_gcs_path}/{file_pattern}"

        if not os.path.exists(local_file_path):
            click.echo(f"⚠️ Local file '{local_file_path}' not found. Skipping push.")
            continue

        if _is_ignored(file_pattern, gitignore_patterns): # Pass file_pattern for gitignore check
            click.echo(f"✅ '{local_file_path}' is correctly ignored by .gitignore.")
        else:
            click.echo(f"⚠️ WARNING: '{local_file_path}' is listed in '{WS_SYNC_FILE}' but NOT in '.gitignore'.", err=True)
            click.echo("  This file contains sensitive or local-only data and should typically not be committed to Git.", err=True)
            if not click.confirm("Do you want to proceed with pushing this file to GCS anyway?"):
                click.echo(f"Skipping '{local_file_path}' due to .gitignore warning.")
                continue
        
        click.echo(f"⬆️ Pushing '{local_file_path}' to '{gcs_object_path}'...")
        if gcs_manager.gcs_cp(local_file_path, gcs_object_path, recursive=True, debug=debug): # Use gcs_manager.gcs_cp
            click.echo(f"✅ Pushed '{local_file_path}'.")
        else:
            click.echo(f"❌ Failed to push '{local_file_path}'.", err=True)

def _is_ignored_by_git_check_ignore(file_path):
    """
    Checks if a file path is ignored by .gitignore using `git check-ignore -q`.
    Returns True if ignored, False otherwise.
    """
    try:
        # git check-ignore -q returns 0 if ignored, 1 if not ignored
        _run_command(['git', 'check-ignore', '-q', file_path], check=False, capture_output=True)
        return True
    except subprocess.CalledProcessError: # Non-zero exit code means not ignored
        return False

@local.command()
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
@click.option('--all', is_flag=True, help='List files ignored by .gitignore but not in .ws-sync.')
def status(debug, all):
    """
    Shows sync status of managed files (local vs. GCS, .gitignore check).
    """
    owner, repo_name = get_git_repo_info()
    if not owner or not repo_name:
        sys.exit(1)

    profile_name = _load_global_config()[0].get('default_gcs_profile', 'default')
    project_id, bucket_name = get_gcs_profile_config(profile_name)
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile_name)
    
    managed_files = _get_managed_files()
    if not managed_files:
        click.echo(f"ℹ️ No files listed in '{WS_SYNC_FILE}'. Nothing to check.")
        # If --all is present, still proceed to check ignored files
        if not all:
            sys.exit(0)

    base_gcs_path = gcs_manager.get_repo_gcs_path()
    if not base_gcs_path:
        click.echo(f"❌ Could not determine GCS path for repository.", err=True)
        sys.exit(1)

    click.echo(f"ℹ️ Checking status for project '{owner}/{repo_name}' in GCS bucket '{gcs_manager.bucket_url}'...")

    local_repo_path = _get_local_repo_path()

    status_data = []

    for file_pattern in managed_files:
        local_file_path = os.path.join(local_repo_path, file_pattern)
        gcs_object_path = f"{base_gcs_path}/{file_pattern}"
        
        ignored_by_gitignore = _is_ignored_by_git_check_ignore(file_pattern)

        # Local file existence and hash
        local_exists = os.path.exists(local_file_path)
        local_hash = None
        if local_exists:
            local_hash = _get_file_hash(local_file_path)
        
        # GCS file existence and hash
        gcs_file_status = _get_gcs_file_status(gcs_manager, gcs_object_path)
        gcs_exists = (gcs_file_status['status'] == "Present")
        gcs_hash = gcs_file_status['metadata'].get('md5_hash')

        sync_status = "N/A"
        if local_exists and gcs_exists:
            if local_hash and gcs_hash and local_hash == gcs_hash:
                sync_status = "In Sync"
            else:
                sync_status = "Content Differs"
        elif local_exists and not gcs_exists:
            sync_status = "Local Only"
        elif not local_exists and gcs_exists:
            sync_status = "GCS Only"
        else:
            sync_status = "Neither Exists"
        
        status_data.append({
            "File": file_pattern,
            "Local Status": "Exists" if local_exists else "Missing",
            "GCS Status": "Exists" if gcs_exists else "Missing",
            "Gitignored": "Yes" if ignored_by_gitignore else "No",
            "Sync Status": sync_status
        })
    
    if status_data:
        click.echo("\n📊 Managed Files Status:")
        click.echo(_generate_ascii_table(status_data))
    
    # --- Logic for --all flag: Ignored but not managed files ---
    if all:
        click.echo("\n--- Checking for Ignored Files Not in .ws-sync (with --all) ---")
        try:
            # Use git ls-files --ignored --exclude-standard to get ignored files
            # -z for null-delimited output, -c for cached, -o for other (untracked)
            ignored_files_output = _run_command(['git', 'ls-files', '--ignored', '--exclude-standard', '--others', '-z'], capture_output=True, check=True).stdout
            all_ignored_files = set(ignored_files_output.split('\0'))
            all_ignored_files.discard('') # Remove empty string if any

            managed_files_set = set(managed_files)
            ignored_but_not_managed = []

            for ignored_file in all_ignored_files:
                if ignored_file not in managed_files_set:
                    ignored_but_not_managed.append({"File": ignored_file})
            
            if ignored_but_not_managed:
                click.echo("\n⚠️ Ignored by .gitignore but NOT listed in .ws-sync:")
                click.echo(_generate_ascii_table(ignored_but_not_managed))
                click.echo("  Consider adding these files to .ws-sync if they are configuration files to be synchronized.")
            else:
                click.echo("✅ No ignored files found that are not also in .ws-sync.")

        except subprocess.CalledProcessError as e:
            click.echo(f"❌ Error running git ls-files to check ignored files: {e}", err=True)
            if e.stderr: click.echo(f"Stderr: {e.stderr}", err=True)
        except Exception as e:
            click.echo(f"❌ An unexpected error occurred while checking ignored files: {e}", err=True)
    
    click.echo("-" * 60)

@local.command(name="setup")
@click.option('--profile', default='default', help='The name of the GCS profile to set up. Defaults to "default".')
@click.option('--project-id', help='The Google Cloud Project ID.')
@click.option('--bucket-name', help='The Google Cloud Storage bucket name.')
def local_setup(profile, project_id, bucket_name):
    """
    Sets up or displays the current GCS configuration for devws local commands.
    """
    gcs_profile_manager = GCSProfileManager()
    global_config, actual_global_config_file = _load_global_config()
    if 'gcs_profiles' not in global_config:
        global_config['gcs_profiles'] = {}

    current_profile_data_in_config = global_config['gcs_profiles'].get(profile, {})

    # --- Find existing labeled resources in GCP for this profile ---
    labeled_projects, labeled_buckets = gcs_profile_manager._find_labeled_gcs_resources(profile)

    # Filter labeled buckets to only those within labeled projects, and get unique (project_id, bucket_name)
    found_gcp_setups = set()
    for p_id in labeled_projects:
        for b_name in labeled_buckets:
            # This is a heuristic, as we don't know which project a globally listed bucket belongs to
            # without more complex queries. Assume if a project is labeled, and a bucket is labeled,
            # they might be related.
            found_gcp_setups.add((p_id, b_name, "labeled_gcp"))

    # Add config entry if it exists
    if current_profile_data_in_config.get('project_id') and current_profile_data_in_config.get('bucket_name'):
        found_gcp_setups.add((current_profile_data_in_config['project_id'], current_profile_data_in_config['bucket_name'], "config"))

    # --- Behavior based on arguments ---
    if project_id or bucket_name:  # Arguments provided
        if found_gcp_setups:
            click.echo(f"❌ Error: Existing GCS setup(s) found for profile '{profile}':")
            for p_id, b_name, source in found_gcp_setups:
                click.echo(f"   - Project: {p_id}, Bucket: {b_name} (Source: {source})")
            click.echo("Please use 'devws local setup clear' to remove existing labels and config before configuring a new one.")
            sys.exit(1)
        else: # No existing setup found, proceed with new configuration
            chosen_project_id = project_id
            chosen_bucket_name = bucket_name
            if not chosen_project_id:
                chosen_project_id = click.prompt("Enter the Google Cloud Project ID")
            if not chosen_bucket_name:
                chosen_bucket_name = click.prompt("Enter the Google Cloud Storage bucket name")

            click.echo(f"⭐ Configuring new setup for profile '{profile}': Project ID='{chosen_project_id}', Bucket='{chosen_bucket_name}'")

            # Verify Bucket exists in Project
            click.echo(f"ℹ️ Verifying if bucket 'gs://{chosen_bucket_name}' exists in project '{chosen_project_id}'...")
            try:
                # Use GCSManager for the actual bucket verification
                # Note: GCSManager's __init__ takes bucket_name, not project_id.
                # The _run_command with -p flag is more direct for project-specific bucket check.
                _run_command(['gsutil', 'ls', '-p', chosen_project_id, f'gs://{chosen_bucket_name}'], capture_output=True, check=True)
                click.echo(f"✅ Bucket 'gs://{chosen_bucket_name}' found in project '{chosen_project_id}'.")
            except Exception as e:
                click.echo(f"❌ Bucket 'gs://{chosen_bucket_name}' not found in project '{chosen_project_id}' or you don't have permissions: {e}", err=True)
                click.echo("Please ensure the bucket name and project ID are correct and you have appropriate permissions.", err=True)
                sys.exit(1)
            
            # Apply labels
            gcs_profile_manager._apply_label_to_project(chosen_project_id, profile)
            gcs_profile_manager._apply_label_to_bucket(chosen_bucket_name, profile)

            # Store in global config
            global_config['gcs_profiles'][profile] = {
                'project_id': chosen_project_id,
                'bucket_name': chosen_bucket_name
            }
            if 'default_gcs_profile' not in global_config:
                global_config['default_gcs_profile'] = profile

            try:
                with open(actual_global_config_file, 'w') as f:
                    yaml.safe_dump(global_config, f, default_flow_style=False)
                click.echo(f"✅ GCS profile '{profile}' configured and saved to {actual_global_config_file}")
            except IOError as e:
                click.echo(f"❌ Error writing to global config file {actual_global_config_file}: {e}", err=True)
                sys.exit(1)
            
    else: # No arguments provided
        if len(found_gcp_setups) == 1:
            p_id, b_name, source = list(found_gcp_setups)[0]
            click.echo(f"✅ Found one existing GCS setup for profile '{profile}':")
            click.echo(f"   - Project: {p_id}, Bucket: {b_name} (Source: {source})")
            click.echo(f"This setup will be used for '{profile}' operations.")
            
            # Update config even if just found (e.g., if only labeled but not in config)
            if not current_profile_data_in_config or \
               current_profile_data_in_config.get('project_id') != p_id or \
               current_profile_data_in_config.get('bucket_name') != b_name:
                
                click.echo(f"ℹ️ Updating global config for profile '{profile}'.")
                global_config['gcs_profiles'][profile] = {
                    'project_id': p_id,
                    'bucket_name': b_name
                }
                if 'default_gcs_profile' not in global_config:
                    global_config['default_gcs_profile'] = profile
                
                try:
                    with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
                        yaml.safe_dump(global_config, f, default_flow_style=False)
                    click.echo(f"✅ GCS profile '{profile}' updated in {GLOBAL_DEVWS_CONFIG_FILE}")
                except IOError as e:
                    click.echo(f"❌ Error writing to global config file {GLOBAL_DEVWS_CONFIG_FILE}: {e}", err=True)
                    sys.exit(1)

        elif len(found_gcp_setups) > 1:
            click.echo(f"❌ Error: Found multiple existing GCS setups for profile '{profile}':")
            for p_id, b_name, source in found_gcp_setups:
                click.echo(f"   - Project: {p_id}, Bucket: {b_name} (Source: {source})")
            click.echo("Please use 'devws local setup clear' to resolve the ambiguity.")
            sys.exit(1)
        else: # No existing setups found
            click.echo(f"⚠️ No existing GCS setup found for profile '{profile}'.")
            if click.confirm("Do you want to set up a new GCS configuration now?"):
                chosen_project_id = click.prompt("Enter the Google Cloud Project ID")
                chosen_bucket_name = click.prompt("Enter the Google Cloud Storage bucket name")

                click.echo(f"⭐ Configuring new setup for profile '{profile}': Project ID='{chosen_project_id}', Bucket='{chosen_bucket_name}'")

                # Verify Bucket exists in Project
                click.echo(f"ℹ️ Verifying if bucket 'gs://{chosen_bucket_name}' exists in project '{chosen_project_id}'...")
                try:
                    _run_command(['gsutil', 'ls', '-p', chosen_project_id, f'gs://{chosen_bucket_name}'], capture_output=True, check=True)
                    click.echo(f"✅ Bucket 'gs://{chosen_bucket_name}' found in project '{chosen_project_id}'.")
                except Exception as e:
                    click.echo(f"❌ Bucket 'gs://{chosen_bucket_name}' not found in project '{chosen_project_id}' or you don't have permissions: {e}", err=True)
                    click.echo("Please ensure the bucket name and project ID are correct and you have appropriate permissions.", err=True)
                    sys.exit(1)
                
                # Apply labels
                gcs_profile_manager._apply_label_to_project(chosen_project_id, profile)
                gcs_profile_manager._apply_label_to_bucket(chosen_bucket_name, profile)

                # Store in global config
                global_config['gcs_profiles'][profile] = {
                    'project_id': chosen_project_id,
                    'bucket_name': chosen_bucket_name
                }
                if 'default_gcs_profile' not in global_config:
                    global_config['default_gcs_profile'] = profile

                try:
                    with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
                        yaml.safe_dump(global_config, f, default_flow_style=False)
                    click.echo(f"✅ GCS profile '{profile}' configured and saved to {GLOBAL_DEVWS_CONFIG_FILE}")
                except IOError as e:
                    click.echo(f"❌ Error writing to global config file {GLOBAL_DEVWS_CONFIG_FILE}: {e}", err=True)
                    sys.exit(1)
            else:
                click.echo("Setup cancelled.")
                sys.exit(0)

@local.command(name="setup-clear")
@click.option('--profile', default='default', help='The name of the GCS profile to clear. Defaults to "default".')
def local_setup_clear(profile):
    """
    Removes GCS labels for the specified profile from all projects and buckets.
    THIS IS A DESTRUCTIVE COMMAND, LABELS ARE PERMANENTLY REMOVED.
    """
    gcs_profile_manager = GCSProfileManager()
    click.echo(f"🗑️ Attempting to clear GCS labels for profile: '{profile}'")

    labeled_projects, labeled_buckets = gcs_profile_manager._find_labeled_gcs_resources(profile)

    if not labeled_projects and not labeled_buckets:
        click.echo(f"ℹ️ No projects or buckets found with label 'ws-sync={profile}'. Nothing to clear.")
        sys.exit(0)

    click.echo(f"⚠️ WARNING: This will remove the 'ws-sync={profile}' label from the following resources:")
    if labeled_projects:
        click.echo("  Projects:")
        for p_id in labeled_projects:
            click.echo(f"    - {p_id}")
    if labeled_buckets:
        click.echo("  Buckets:")
        for b_name in labeled_buckets:
            click.echo(f"    - {b_name}")
    
    if not click.confirm("Are you absolutely sure you want to proceed with clearing these labels? This action cannot be undone."):
        click.echo("Operation cancelled.")
        sys.exit(0)

    success = True
    # Remove labels from projects
    for p_id in labeled_projects:
        if not gcs_profile_manager._remove_label_from_project(p_id, profile):
            success = False
    
    # Remove labels from buckets
    for b_name in labeled_buckets:
        if not gcs_profile_manager._remove_label_from_bucket(b_name, profile):
            success = False
    
    # Also remove from global config
    global_config, _ = _load_global_config()
    if 'gcs_profiles' in global_config and profile in global_config['gcs_profiles']:
        del global_config['gcs_profiles'][profile]
        if global_config.get('default_gcs_profile') == profile:
            del global_config['default_gcs_profile']
            click.echo(f"ℹ️ Removed '{profile}' as default GCS profile from config.")
        try:
            with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
                yaml.safe_dump(global_config, f, default_flow_style=False)
            click.echo(f"✅ Profile '{profile}' removed from global configuration.")
        except IOError as e:
            click.echo(f"❌ Error writing to global config file {GLOBAL_DEVWS_CONFIG_FILE}: {e}", err=True)
            success = False
    
    if success:
        click.echo(f"✅ Successfully cleared GCS labels and configuration for profile '{profile}'.")
    else:
        click.echo(f"❌ Failed to clear all GCS labels and configuration for profile '{profile}'. See errors above.", err=True)
        sys.exit(1)

@local.command(name="clear")
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def local_clear(debug):
    """
    Deletes all project-scoped files for the current repository from GCS.
    Requires user confirmation. THIS IS A DESTRUCTIVE COMMAND.
    """
    owner, repo_name = get_git_repo_info()
    if not owner or not repo_name:
        sys.exit(1)

    profile_name = _load_global_config()[0].get('default_gcs_profile', 'default')
    project_id, bucket_name = get_gcs_profile_config(profile_name)
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile_name)
    
    base_gcs_path = gcs_manager.get_repo_gcs_path()
    if not base_gcs_path:
        click.echo(f"❌ Could not determine GCS path for repository.", err=True)
        sys.exit(1)

    click.echo(f"⚠️  WARNING: This will delete ALL project-scoped files for '{owner}/{repo_name}'")
    click.echo(f"   from GCS path: '{base_gcs_path}/*'")
    if not click.confirm("Are you sure you want to proceed with this destructive operation?"):
        click.echo("Operation cancelled.")
        sys.exit(0)
    
    click.echo(f"🗑️ Deleting files from {base_gcs_path}/...")
    try:
        # Use gcs_manager.gcs_rm to remove all objects under the project path
        gcs_manager.gcs_rm(f'{base_gcs_path}/*', recursive=True, debug=debug)
        click.echo(f"✅ Successfully deleted all project-scoped files for '{owner}/{repo_name}' from GCS.")
    except Exception as e:
        click.echo(f"❌ Failed to delete files from GCS: {e}", err=True)
        sys.exit(1)
