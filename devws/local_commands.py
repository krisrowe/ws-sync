import click
import os
import sys
import fnmatch
import hashlib
import glob
import yaml
import json
import subprocess
from datetime import datetime

from devws_cli.utils import (
    _run_command, _load_global_config, GLOBAL_DEVWS_CONFIG_FILE, get_git_repo_info, 
    get_gcs_profile_config, _get_file_hash, _get_gcs_file_status, 
    _get_local_file_status, _generate_ascii_table
)
from devws_cli.gcs_manager import GCSManager
from devws_cli.gcs_profile_manager import GCSProfileManager

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
        if fnmatch.fnmatch(file_path, pattern):
            return True
        if pattern.endswith('/'):
            if file_path == pattern.rstrip('/'):
                return True
            if file_path.startswith(pattern):
                return True
        if os.path.isdir(file_path) and fnmatch.fnmatch(os.path.basename(file_path), pattern):
            return True
    return False

def _get_dry_run_results(gcs_manager, managed_files, base_gcs_path, gitignore_patterns, local_repo_path, force):
    """
    Generates dry run results for the pull command.
    """
    dry_run_results = []
    for file_pattern in managed_files:
        local_file_path = os.path.join(local_repo_path, file_pattern)
        gcs_object_path = f"{base_gcs_path}/{file_pattern}"
        local_file_status = _get_local_file_status(local_file_path)
        gcs_file_status = _get_gcs_file_status(gcs_manager, gcs_object_path)
        local_status_str = local_file_status['status']
        if local_file_status['status'] == "Present" and local_file_status['type'] == "File":
            if gcs_file_status['status'] == "Present" and gcs_file_status['type'] == "File":
                local_hash = local_file_status['metadata'].get('md5_hash')
                gcs_hash = gcs_file_status['metadata'].get('md5_hash')
                if local_hash and gcs_hash:
                    if local_hash == gcs_hash:
                        local_status_str = "Present (Same)"
                    else:
                        local_status_str = "Present (Different)"
                else:
                    local_status_str = "Present (Different)"
            else:
                local_status_str = "Present"
        elif local_file_status['status'] == "Present" and local_file_status['type'] == "Directory":
            local_status_str = "Present (Dir)"
        action = "None"
        ignored_by_gitignore = "Yes" if _is_ignored(file_pattern, gitignore_patterns) else "No"
        if ignored_by_gitignore == "Yes":
            action = "Skip (Ignored)"
        elif gcs_file_status['status'] == "Present" and gcs_file_status['type'] == "File":
            if local_file_status['status'] == "Present" and local_file_status['type'] == "File":
                if force:
                    action = "Overwrite"
                else:
                    action = "Skip (Local Exists)"
            elif local_file_status['status'] == "Present" and local_file_status['type'] == "Directory":
                action = "Conflict (GCS file, local dir)"
            else:
                action = "Pull"
        elif gcs_file_status['status'] == "Present" and gcs_file_status['type'] == "Directory":
            if local_file_status['status'] == "Present" and local_file_status['type'] == "File":
                action = "Conflict (GCS dir, local file)"
            else:
                action = "Sync Directory"
        else:
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

def _is_ignored_by_git_check_ignore(file_path):
    """
    Checks if a file path is ignored by .gitignore using `git check-ignore -q`.
    """
    try:
        _run_command(['git', 'check-ignore', '-q', file_path], check=False, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

@click.group()
def local():
    """Manages project-specific configuration files."""
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