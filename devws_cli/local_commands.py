import click
import os
import sys
import fnmatch # For glob-style pattern matching
import hashlib # For file content hashing
import glob # For glob pattern matching
import yaml # For YAML parsing/dumping
import json # For parsing gcloud output
import subprocess
import sys # Added this line
from datetime import datetime # For handling timestamps
from devws_cli.utils import _run_command, _load_global_config, GLOBAL_DEVWS_CONFIG_FILE
from devws_cli.managers.locals_manager import LocalsManager

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


def _get_gcs_file_status(gcs_object_path):
    """
    Determines the existence, type (file/directory), and relevant metadata
    of a given path in Google Cloud Storage.

    Args:
        gcs_object_path (str): The full gs:// path to the GCS object or prefix.

    Returns:
        dict: A dictionary with 'status', 'type', and 'metadata'.
              metadata includes 'last_modified_timestamp' (ISO format) and 'md5_hash'.
    """
    status = "Not Present"
    file_type = "N/A"
    metadata = {}

    # First, try to see if it's a directory (prefix) by listing contents
    try:
        command_dir_check = ['gsutil', 'ls', f'{gcs_object_path.rstrip("/")}/**']
        result_dir_check = _run_command(command_dir_check, capture_output=True, check=True)
        if result_dir_check.stdout.strip():
            # If listing contents succeeds and returns output, it's a directory
            return {
                "status": "Present",
                "type": "Directory",
                "metadata": {}
            }
    except subprocess.CalledProcessError:
        pass # Not a directory, or empty directory, proceed to check if it's a file

    # If not identified as a directory, try to get file metadata using gcloud storage
    try:
        # Use gcloud storage objects describe --format=json for structured output
        command_file_check = ['gcloud', 'storage', 'objects', 'describe', gcs_object_path, '--format=json']
        result_file_check = _run_command(command_file_check, capture_output=True, check=True)
        output = result_file_check.stdout

        # Parse JSON output
        import json as json_module
        try:
            obj = json_module.loads(output)
            status = "Present"
            file_type = "File"
            
            # Extract metadata from JSON (md5_hash is at top level)
            if 'update_time' in obj:
                metadata['last_modified_timestamp'] = obj['update_time']
            if 'md5_hash' in obj:
                # md5_hash is already base64-encoded in GCS
                metadata['md5_hash'] = obj['md5_hash']
            
            return {
                "status": status,
                "type": file_type,
                "metadata": metadata
            }
        except json_module.JSONDecodeError as e:
            click.echo(f"❌ Error parsing JSON from gcloud storage objects describe: {e}", err=True)
            return {
                "status": "Unknown Error",
                "type": "N/A",
                "metadata": {}
            }
    except subprocess.CalledProcessError as e:
        # If both directory check and file check failed, then it's not present.
        # This covers cases where gsutil ls -L returns "No URLs matched".
        return {
            "status": "Not Present",
            "type": "N/A",
            "metadata": {}
        }
    except Exception as e:
        # Catch any other unexpected errors
        click.echo(f"❌ Unexpected error getting GCS status for {gcs_object_path}: {e}", err=True)
        return {
            "status": "Unknown Error",
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

    # Define columns and their display names
    columns = [
        ("file_pattern", "File Pattern"),
        ("local_status", "Local Status"),
        ("gcs_status", "GCS Status"),
        ("ignored_by_gitignore", "Ignored by .gitignore"),
        ("action", "Action")
    ]
    
    headers = [col_display for _, col_display in columns]

    # Calculate maximum column widths
    column_widths = {key: len(display_name) for key, display_name in columns}
    for row in data:
        for key, _ in columns:
            column_widths[key] = max(column_widths[key], len(str(row.get(key, ''))))
    
    # Build the header row
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
    locals_manager = LocalsManager()
    # Check if inside a Git repository
    owner, repo_name = locals_manager.get_git_repo_info()
    if not owner or not repo_name:
        click.echo("❌ Not inside a Git repository. 'devws local init' must be run from a Git repository root.", err=True)
        sys.exit(1)

    ws_sync_path = _get_ws_sync_path()

    if os.path.exists(ws_sync_path):
        click.echo(f"⚠️ '{WS_SYNC_FILE}' already exists in this repository.", err=True)
        if not click.confirm("Do you want to overwrite it?"):
            click.echo("Operation cancelled.")
            sys.exit(0)

    global_config, _ = _load_global_config()
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

def _get_dry_run_results(managed_files, base_gcs_path, gitignore_patterns, local_repo_path, force):
    """
    Generates dry run results for the pull command.
    """
    dry_run_results = []

    for file_pattern in managed_files:
        local_file_path = os.path.join(local_repo_path, file_pattern)
        gcs_object_path = f"{base_gcs_path}/{file_pattern}"
        
        # Get local and GCS file status
        local_file_status = _get_local_file_status(local_file_path)
        gcs_file_status = _get_gcs_file_status(gcs_object_path)

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
            "action": action,
            "local_details": local_file_status,
            "gcs_details": gcs_file_status
        })
    
    return dry_run_results

@local.command()
@click.option('--force', is_flag=True, help='Overwrite local changes if conflicts exist.')
@click.option('--dry-run', is_flag=True, help='Perform a dry run without actually pulling files, showing what would happen.')
@click.option('--json', 'json_output', is_flag=True, help='Output dry run results as JSON.')
def pull(force, dry_run, json_output):
    """
    Pulls all files listed in .ws-sync from GCS to the local project directory.
    """
    locals_manager = LocalsManager(silent=json_output)
    owner, repo_name = locals_manager.get_git_repo_info()
    if not owner or not repo_name:
        sys.exit(1)

    # Use locals_manager to get project_id and bucket_name from config
    project_id, bucket_name = locals_manager.get_gcs_profile_config()
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    bucket_url = f"gs://{bucket_name}"

    managed_files = _get_managed_files()
    if not managed_files:
        click.echo(f"ℹ️ No files listed in '{WS_SYNC_FILE}'. Nothing to pull.")
        sys.exit(0)

    base_gcs_path = f"{bucket_url}/projects/{owner}/{repo_name}"
    
    if dry_run:
        if not json_output: # Only echo if not JSON output
            click.echo(f"ℹ️ Performing dry run for project '{owner}/{repo_name}' from GCS bucket '{bucket_url}'...")
        
        gitignore_patterns = _get_gitignore_patterns()
        local_repo_path = _get_local_repo_path()

        dry_run_results = _get_dry_run_results(
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
    click.echo(f"ℹ️ Pulling files for project '{owner}/{repo_name}' from GCS bucket '{bucket_url}'...")

    local_repo_path = _get_local_repo_path()

    for file_pattern in managed_files:
        local_file_path = os.path.join(local_repo_path, file_pattern)
        gcs_object_path = f"{base_gcs_path}/{file_pattern}"

        # Check if local file exists and if we should skip it
        if os.path.exists(local_file_path) and not force:
            # Skip force check for directories - always sync them
            if os.path.isdir(local_file_path):
                # Directories are synced recursively, proceed with pull
                pass
            else:
                # For files, check if it's the same as GCS version
                local_file_status = _get_local_file_status(local_file_path)
                gcs_file_status = _get_gcs_file_status(gcs_object_path)
                
                # Skip the warning if files have identical content (same MD5 hash)
                if (local_file_status.get('type') == 'File' and 
                    gcs_file_status.get('type') == 'File' and
                    local_file_status.get('metadata', {}).get('md5_hash') == 
                    gcs_file_status.get('metadata', {}).get('md5_hash')):
                    # Files are identical, skip silently
                    click.echo(f"✅ '{local_file_path}' is already up to date.")
                    continue
                
                # Files are different, show warning
                click.echo(f"⚠️ Local file '{local_file_path}' already exists. Use --force to overwrite.")
                continue
        
        click.echo(f"⬇️ Pulling '{gcs_object_path}' to '{local_file_path}'...")
        if locals_manager.gcs_cp(gcs_object_path, local_file_path):
            click.echo(f"✅ Pulled '{local_file_path}'.")
        else:
            click.echo(f"❌ Failed to pull '{local_file_path}'.", err=True)

@local.command()
@click.option('--force', is_flag=True, help='Overwrite GCS version if conflicts exist.')
def push(force):
    """
    Pushes all files listed in .ws-sync from the local project directory to GCS.
    """
    locals_manager = LocalsManager()
    owner, repo_name = locals_manager.get_git_repo_info()
    if not owner or not repo_name:
        sys.exit(1)

    # Use locals_manager to get project_id and bucket_name from config
    project_id, bucket_name = locals_manager.get_gcs_profile_config()
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    bucket_url = f"gs://{bucket_name}"
    
    managed_files = _get_managed_files()
    if not managed_files:
        click.echo(f"ℹ️ No files listed in '{WS_SYNC_FILE}'. Nothing to push.")
        sys.exit(0)

    base_gcs_path = f"{bucket_url}/projects/{owner}/{repo_name}"
    click.echo(f"ℹ️ Pushing files for project '{owner}/{repo_name}' to GCS bucket '{bucket_url}'...")

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
        if locals_manager.gcs_cp(local_file_path, gcs_object_path):
            click.echo(f"✅ Pushed '{local_file_path}'.")
        else:
            click.echo(f"❌ Failed to push '{local_file_path}'.", err=True)

@local.command()
def status():
    """
    Shows sync status of managed files (local vs. GCS, .gitignore check).
    """
    locals_manager = LocalsManager()
    owner, repo_name = locals_manager.get_git_repo_info()
    if not owner or not repo_name:
        sys.exit(1)

    # Use locals_manager to get project_id and bucket_name from config
    project_id, bucket_name = locals_manager.get_gcs_profile_config()
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    bucket_url = f"gs://{bucket_name}"
    
    managed_files = _get_managed_files()
    if not managed_files:
        click.echo(f"ℹ️ No files listed in '{WS_SYNC_FILE}'. Nothing to check.")
        sys.exit(0)

    base_gcs_path = f"{bucket_url}/projects/{owner}/{repo_name}"
    click.echo(f"ℹ️ Checking status for project '{owner}/{repo_name}' in GCS bucket '{bucket_url}'...")

    gitignore_patterns = _get_gitignore_patterns()
    local_repo_path = _get_local_repo_path()

    for file_pattern in managed_files:
        local_file_path = os.path.join(local_repo_path, file_pattern)
        gcs_object_path = f"{base_gcs_path}/{file_pattern}"
        
        click.echo(f"\n--- File: {local_file_path} ---")

        # .gitignore check
        if _is_ignored(file_pattern, gitignore_patterns): # Pass file_pattern for gitignore check
            click.echo(f"  ✅ Git Status: Correctly ignored by .gitignore.")
        else:
            click.echo(f"  ⚠️ Git Status: WARNING! Not ignored by .gitignore. Consider adding '{local_file_path}' to .gitignore.")

        # Local file existence and hash
        local_exists = os.path.exists(local_file_path)
        local_hash = None
        if local_exists:
            click.echo(f"  ✅ Local Status: Exists.")
            local_hash = _get_file_hash(local_file_path)
            click.echo(f"  Local Hash: {local_hash}")
        else:
            click.echo(f"  ❌ Local Status: Does NOT exist.")
        
        # GCS file existence and hash (requires fetching metadata)
        gcs_exists = False
        gcs_hash = None
        try:
            # Use gsutil stat to get the status of the GCS object
            # gsutil stat doesn't directly give SHA256 easily, so we'll check existence for now.
            # Full hash comparison is a future enhancement.
            _run_command(['gsutil', 'stat', gcs_object_path], capture_output=True)
            gcs_exists = True
            click.echo(f"  ✅ GCS Status: Exists at {gcs_object_path}.")
        except subprocess.CalledProcessError:
            click.echo(f"  ❌ GCS Status: Does NOT exist at {gcs_object_path}.")
        
        # Basic sync status
        if local_exists and gcs_exists:
            # For a true sync status, we'd compare hashes. This is a placeholder.
            click.echo("  ➡️ Sync Status: Local and GCS versions exist. (Content comparison is a future enhancement).")
        elif local_exists and not gcs_exists:
            click.echo("  ➡️ Sync Status: Local file exists, but not in GCS. Consider 'devws local push'.")
        elif not local_exists and gcs_exists:
            click.echo("  ➡️ Sync Status: GCS file exists, but not locally. Consider 'devws local pull'.")
        else:
            click.echo("  ➡️ Sync Status: Neither local nor GCS file exists.")

@local.command(name="setup")
@click.option('--profile', default='default', help='The name of the GCS profile to set up. Defaults to "default".')
@click.option('--project-id', help='The Google Cloud Project ID.')
@click.option('--bucket-name', help='The Google Cloud Storage bucket name.')
def local_setup(profile, project_id, bucket_name):
    """
    Sets up or displays the current GCS configuration for devws local commands.
    """
    locals_manager = LocalsManager()
    global_config, actual_global_config_file = _load_global_config()
    if 'gcs_profiles' not in global_config:
        global_config['gcs_profiles'] = {}

    current_profile_data_in_config = global_config['gcs_profiles'].get(profile, {})

    # --- Find existing labeled resources in GCP for this profile ---
    labeled_projects, labeled_buckets = locals_manager._find_labeled_gcs_resources(profile)

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
                _run_command(['gsutil', 'ls', '-p', chosen_project_id, f'gs://{chosen_bucket_name}'], capture_output=True, check=True)
                click.echo(f"✅ Bucket 'gs://{chosen_bucket_name}' found in project '{chosen_project_id}'.")
            except Exception as e:
                click.echo(f"❌ Bucket 'gs://{chosen_bucket_name}' not found in project '{chosen_project_id}' or you don't have permissions: {e}", err=True)
                click.echo("Please ensure the bucket name and project ID are correct and you have appropriate permissions.", err=True)
                sys.exit(1)
            
            # Apply labels
            locals_manager._apply_label_to_project(chosen_project_id, profile)
            locals_manager._apply_label_to_bucket(chosen_bucket_name, profile)

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
                locals_manager._apply_label_to_project(chosen_project_id, profile)
                locals_manager._apply_label_to_bucket(chosen_bucket_name, profile)

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
    locals_manager = LocalsManager()
    click.echo(f"🗑️ Attempting to clear GCS labels for profile: '{profile}'")

    labeled_projects, labeled_buckets = locals_manager._find_labeled_gcs_resources(profile)

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
        if not locals_manager._remove_label_from_project(p_id, profile):
            success = False
    
    # Remove labels from buckets
    for b_name in labeled_buckets:
        if not locals_manager._remove_label_from_bucket(b_name, profile):
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
def local_clear():
    """
    Deletes all project-scoped files for the current repository from GCS.
    Requires user confirmation. THIS IS A DESTRUCTIVE COMMAND.
    """
    locals_manager = LocalsManager()
    owner, repo_name = locals_manager.get_git_repo_info()
    if not owner or not repo_name:
        sys.exit(1)

    # Use locals_manager to get project_id and bucket_name from config
    project_id, bucket_name = locals_manager.get_gcs_profile_config()
    if not project_id or not bucket_name:
        click.echo(f"❌ GCS configuration not found. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    bucket_url = f"gs://{bucket_name}"
    
    base_gcs_path = f"{bucket_url}/projects/{owner}/{repo_name}"
    
    click.echo(f"⚠️  WARNING: This will delete ALL project-scoped files for '{owner}/{repo_name}'")
    click.echo(f"   from GCS path: '{base_gcs_path}/*'")
    if not click.confirm("Are you sure you want to proceed with this destructive operation?"):
        click.echo("Operation cancelled.")
        sys.exit(0)
    
    click.echo(f"🗑️ Deleting files from {base_gcs_path}/...")
    try:
        # Use gsutil rm -r to remove all objects under the project path
        _run_command(['gsutil', '-m', 'rm', '-r', f'{base_gcs_path}/*'])
        click.echo(f"✅ Successfully deleted all project-scoped files for '{owner}/{repo_name}' from GCS.")
    except Exception as e:
        click.echo(f"❌ Failed to delete files from GCS: {e}", err=True)
        sys.exit(1)
