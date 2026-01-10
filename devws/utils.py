import subprocess
import click
import os
import sys
import hashlib
import re # Import re for regular expressions
import yaml # Import yaml for global config
from datetime import datetime
import fnmatch

# Global status tracking
STEP_STATUS = {}
STEP_CATEGORY = {}
STEP_COUNT = 0

# Global Configuration Paths
# WS_SYNC_CONFIG env var now points to the CONFIG DIRECTORY (default: ~/.config/devws)
GLOBAL_DEVWS_CONFIG_DIR = os.environ.get("WS_SYNC_CONFIG", os.path.expanduser("~/.config/devws"))
GLOBAL_DEVWS_CONFIG_FILE = os.path.join(GLOBAL_DEVWS_CONFIG_DIR, "config.yaml")

def _run_command(command, check=True, capture_output=False, shell=False, cwd=None, env=None, debug=False, dry_run=False, is_idempotent_check=False):
    """
    Wrapper for subprocess.run to execute shell commands, with dry-run support.
    
    Args:
        debug: If True, shows error messages when commands fail.
        dry_run: If True, simulates command execution without making changes.
        is_idempotent_check: If True, the command will run even in dry_run mode.
    """
    if dry_run and not is_idempotent_check:
        command_str = ' '.join(command) if isinstance(command, list) else command
        click.echo(f"  [DRY RUN] Would execute: {command_str}")
        # Return a mock successful result
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    if env is None:
        env = os.environ.copy() # Use a copy of the current environment by default

    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=True,
            shell=shell,
            cwd=cwd,
            env=env # Pass the environment
        )
        return result
    except subprocess.CalledProcessError as e:
        # This block is only reached if check=True and command failed
        if debug:
            click.echo(f"Command failed: {' '.join(command) if isinstance(command, list) else command}", err=True)
            if capture_output:
                click.echo(f"Stdout: {e.stdout}", err=True)
                click.echo(f"Stderr: {e.stderr}", err=True)
        raise # Re-raise the exception as check=True implies we want it to fail
    except FileNotFoundError:
        if debug:
            click.echo(f"Command not found: {command[0] if isinstance(command, list) else command.split()[0]}", err=True)
        raise

def _log_step(step_name, status, message="", category=None):
    """
    Logs a step with its status and optional message.
    Args:
        step_name: Name of the step
        status: Status string (PASS, FAIL, SKIP, COMPLETED, VERIFIED, READY, DISABLED, PARTIAL)
        message: Optional message to display
        category: Optional category (core, common, development, custom)
    """
    global STEP_COUNT
    STEP_COUNT += 1
    STEP_STATUS[step_name] = status
    if category:
        STEP_CATEGORY[step_name] = category

    status_emoji = {
        "PASS": "✅",
        "COMPLETED": "✅",
        "VERIFIED": "✅",
        "SKIP": "⏭️",
        "DISABLED": "🚫",
        "PARTIAL": "⚠️",
        "FAIL": "❌",
        "READY": "🔵", # New status for dry-run
    }.get(status, "❓")

    status_text = {
        "PASS": "PASSED",
        "COMPLETED": "COMPLETED (just finished)",
        "VERIFIED": "VERIFIED (already done)",
        "SKIP": "SKIPPED (not applicable)",
        "DISABLED": "DISABLED (configuration)",
        "PARTIAL": "PARTIAL (needs attention)",
        "FAIL": "FAILED",
        "READY": "READY (dry-run)", # New status for dry-run
    }.get(status, "UNKNOWN")

    click.echo(f"{status_emoji} {step_name} - {status_text}")
    if message:
        click.echo(f"  → {message}")

def _print_final_report():
    """
    Prints the final setup report with category subheadings.
    """
    click.echo("\n" + "=" * 60)
    click.echo("SETUP REPORT".center(60))
    click.echo("=" * 60)
    click.echo(f"{'STEP':<40} {'STATUS':<10}")
    click.echo("-" * 60)

    # Group steps by category
    categorized_steps = {}
    for step, status in STEP_STATUS.items():
        category = STEP_CATEGORY.get(step, "custom")
        if category not in categorized_steps:
            categorized_steps[category] = []
        categorized_steps[category].append((step, status))
    
    # Print in category order: core, common, development, custom
    category_order = ["core", "common", "development", "custom"]
    category_names = {
        "core": "Core",
        "common": "Common",
        "development": "Development",
        "custom": "Custom"
    }
    
    for category in category_order:
        if category in categorized_steps:
            # Print category subheading
            click.echo(f"\n{category_names[category].upper()}")
            for step, status in categorized_steps[category]:
                status_display = {
                    "PASS": "✅ PASS",
                    "COMPLETED": "✅ COMPLETED",
                    "VERIFIED": "✅ VERIFIED",
                    "SKIP": "⏭️  SKIP",
                    "DISABLED": "🚫 DISABLED",
                    "PARTIAL": "⚠️  PARTIAL",
                    "FAIL": "❌ FAIL",
                    "READY": "🔵 READY",
                }.get(status, f"❓ {status}")
                click.echo(f"{step:<40} {status_display:<10}")

    completed_count = sum(1 for s in STEP_STATUS.values() if s == "COMPLETED")
    verified_count = sum(1 for s in STEP_STATUS.values() if s == "VERIFIED")
    skip_count = sum(1 for s in STEP_STATUS.values() if s == "SKIP")
    disabled_count = sum(1 for s in STEP_STATUS.values() if s == "DISABLED")
    partial_count = sum(1 for s in STEP_STATUS.values() if s == "PARTIAL")
    fail_count = sum(1 for s in STEP_STATUS.values() if s == "FAIL")

    click.echo("-" * 60)
    summary_parts = []
    if completed_count > 0: summary_parts.append(f"{completed_count} completed")
    if verified_count > 0: summary_parts.append(f"{verified_count} verified")
    if skip_count > 0: summary_parts.append(f"{skip_count} skipped")
    if disabled_count > 0: summary_parts.append(f"{disabled_count} disabled")
    if partial_count > 0: summary_parts.append(f"{partial_count} partial")
    if fail_count > 0: summary_parts.append(f"{fail_count} failed")

    if summary_parts:
        click.echo(f"SUMMARY: {', '.join(summary_parts)}")
    else:
        click.echo("SUMMARY: No steps processed")
    click.echo("=" * 60)

    _print_action_items()

def _print_action_items():
    """
    Prints action items based on failed or partial steps.
    """
    has_actions = False
    action_items = []

    for step, status in STEP_STATUS.items():
        if status in ["FAIL", "PARTIAL"]:
            has_actions = True
            if step == "GitHub CLI Installation":
                action_items.append("• Install GitHub CLI manually: https://cli.github.com/")
            elif step == "Google Cloud CLI Installation":
                action_items.append("• Install Google Cloud CLI manually: https://cloud.google.com/sdk/docs/install")
            elif step == "Cursor Agent Installation":
                action_items.append("• Fix npm permissions or install cursor-agent manually")
            elif step == "Gemini CLI Installation":
                action_items.append("• Fix npm permissions or install @google/gemini-cli manually")
            elif step == "Python Installation":
                action_items.append("• Install Python or later manually") # Need to get MIN_VERSION from config
            elif step == "Node.js Installation":
                action_items.append("• Install Node.js or later manually") # Need to get MIN_VERSION from config
            elif step == "Environment File Detection":
                action_items.append("• Create ~/.env file with your API keys")
            elif step == "Secrets Backup Validation":
                action_items.append("• Run 'devws env backup' to backup your environment to Google Secrets Manager")
            elif step == "Current Session Environment Loading":
                action_items.append("• Check ~/.env file syntax and permissions")
            # Add more specific action items as needed

    if has_actions:
        click.echo("\nACTION ITEMS:")
        click.echo("-" * 60)
        for item in action_items:
            click.echo(item)
        click.echo("-" * 60)

def _load_config_from_repo(repo_dir):
    """
    Loads configuration from config.yaml file or config.yaml.example within the repository.
    Returns a dictionary of config values.
    """
    config = {}
    config_file = os.path.join(repo_dir, 'config.yaml')
    config_example_file = os.path.join(repo_dir, 'config.yaml.example') # Keep .config.example for now, will rename later

    # Default values for repo-level config
    default_config = {
        "components": {
            "github": {"enabled": True, "tier": 2},
            "google_cloud_cli": {"enabled": True, "tier": 2},
            "python": {"enabled": True, "min_version": "3.9", "tier": 2},
            "nodejs": {"enabled": True, "min_version": "20", "tier": 2},
            "cursor_agent": {"enabled": True, "tier": 2},
            "gemini_cli": {"enabled": True, "tier": 2},
            "env_setup": {"enabled": True, "tier": 1},
            "proj_local_config_sync": {
                "enabled": True,
                "local_sync_candidates": ["*.env"],
                "bucket_name": "", # Default empty
                "tier": 1
            },
        },
        "project_id": "", # Default empty, now lowercase
        "custom_components": [] # New: Define default for custom components
    }
    config.update(default_config)

    if not os.path.exists(config_file) and os.path.exists(config_example_file):
        click.echo(f"Creating {config_file} from {config_example_file}...")
        _run_command(['cp', config_example_file, config_file])
        click.echo(f"Please edit {config_file} to customize your settings.")
        # Load from the newly copied file
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    _deep_update(config, user_config) # Deep merge user config

    elif os.path.exists(config_file):
        click.echo(f"Configuration loaded from {config_file}")
        with open(config_file, 'r') as f:
            user_config = yaml.safe_load(f)
            if user_config:
                _deep_update(config, user_config) # Deep merge user config
    else:
        click.echo("Warning: No config.yaml file found. Using default settings...")
        # config already has default_config

    return config

def _deep_update(base_dict, update_dict):
    """
    Recursively updates a dictionary.
    Used to merge default config with user-provided config.
    """
    for key, value in update_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            base_dict[key] = _deep_update(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict

def _update_bashrc(snippet, identifier, dry_run=False):
    """
    Adds a snippet to ~/.bashrc if it's not already present, identified by a unique string.
    """
    bashrc_path = os.path.expanduser("~/.bashrc")
    try:
        with open(bashrc_path, 'r') as f:
            content = f.read()
            
        if identifier not in content:
            if dry_run:
                click.echo(f"  [DRY RUN] Would append to {bashrc_path}:")
                for line in snippet.splitlines():
                    if line.strip():
                        click.echo(f"    {line}")
                return True # Indicate change would happen
            
            with open(bashrc_path, 'a') as f:
                f.write(f"\n# {identifier}\n{snippet}\n")
                return True
        return False
    except IOError as e:
        click.echo(f"Error updating {bashrc_path}: {e}", err=True)
        return False

def _get_os_type():
    """
    Determines the operating system type.
    """
    if sys.platform.startswith('darwin'):
        return "darwin"
    elif sys.platform.startswith('linux'):
        return "linux-gnu"
    return "unknown"

def _validate_secrets_manager_backup(repo_config):
    """
    Validates the secrets backup status with Google Secrets Manager.
    """
    env_file = os.path.expanduser("~/.env")
    project_id = repo_config.get("project_id") # Get from repo_config (config.yaml)

    if not project_id:
        _log_step("Secrets Backup Validation", "SKIP", "Set 'project_id' in config.yaml to enable secrets backup validation")
        return False

    if not os.path.exists(env_file):
        _log_step("Secrets Backup Validation", "FAIL", f"~/.env file not found at {env_file}")
        return False

    try:
        _run_command(['gcloud', 'auth', 'list'], check=True, capture_output=True)
    except Exception:
        _log_step("Secrets Backup Validation", "FAIL", "gcloud not authenticated.")
        return False

    try:
        _run_command(['gcloud', 'secrets', 'describe', 'dotenv-backup', '--project', project_id], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        _log_step("Secrets Backup Validation", "FAIL", "Secret 'dotenv-backup' not found in Google Secrets Manager.")
        return False

    try:
        local_content = open(env_file, 'rb').read()
        local_hash = hashlib.sha256(local_content).hexdigest()

        stored_result = _run_command(
            ['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret', 'dotenv-backup', '--project', project_id],
            check=True, capture_output=True
        )
        stored_content = stored_result.stdout.encode('utf-8') # Assuming UTF-8 for secret content
        stored_hash = hashlib.sha256(stored_content).hexdigest()

        if local_hash == stored_hash:
            _log_step("Secrets Backup Validation", "PASS")
            return True
        else:
            _log_step("Secrets Backup Validation", "PARTIAL", "~/.env file is out of sync with Google Secrets Manager.")
            return False
    except Exception as e:
        _log_step("Secrets Backup Validation", "FAIL", f"Error comparing secrets: {e}")
        return False

# Removed _get_gcs_config and _find_labeled_gcs_resources
# Removed _gcs_cp and _get_git_repo_info (these were not used in setup_commands.py directly)

def _load_global_config(silent=False, debug=False):
    """
    Loads global devws configuration in a layered approach:
    1. Base config from devws_cli/config.default.yaml (tool's default).
    2. User-specific config from GLOBAL_DEVWS_CONFIG_FILE (overrides base).

    Returns a tuple (merged_config_dict, actual_global_config_file_path).
    
    Args:
        silent: If True, suppresses informational output
        debug: If True, shows debug output
    """
    # Initialize with an empty dictionary for merging
    merged_config = {}

    # --- 1. Load Base Config (from devws_cli/config.default.yaml) ---
    base_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.default.yaml")
    if os.path.exists(base_config_path):
        try:
            with open(base_config_path, 'r') as f:
                base_config = yaml.safe_load(f)
                if base_config:
                    _deep_update(merged_config, base_config)
            if debug:
                click.echo(f"DEBUG: Loaded base config from: {base_config_path}")
        except yaml.YAMLError as e:
            click.echo(f"⚠️ Warning: Error parsing base config file {base_config_path}: {e}", err=True)
            # Continue with an empty base config if parsing fails

    # --- 2. Load User Config (from GLOBAL_DEVWS_CONFIG_FILE) ---
    actual_global_config_file = GLOBAL_DEVWS_CONFIG_FILE
    if debug:
        click.echo(f"DEBUG: Using user global config file: {actual_global_config_file}")

    if os.path.exists(actual_global_config_file):
        try:
            with open(actual_global_config_file, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    _deep_update(merged_config, user_config) # User config overrides base
            if debug:
                click.echo(f"DEBUG: Loaded user global config from: {actual_global_config_file}")
        except yaml.YAMLError as e:
            click.echo(f"⚠️ Warning: Error parsing user global config file {actual_global_config_file}: {e}", err=True)
            # Continue with current merged_config if parsing fails
    elif not silent:
        if debug:
            click.echo(f"DEBUG: User global config file not found at {actual_global_config_file}. Using defaults and base config.")
    
    # Ensure default values are present after merging, if not set in either config
    # This acts as a final fallback for essential keys
    if 'gcs_profiles' not in merged_config:
        merged_config['gcs_profiles'] = {}
    if 'local_sync_candidates' not in merged_config:
        merged_config['local_sync_candidates'] = ['*.env']
    if 'default_gcp_project_id' not in merged_config:
        merged_config['default_gcp_project_id'] = ''

    return merged_config, actual_global_config_file

def _get_ws_sync_label_key():
    """
    Returns the label key used for GCS synchronization.
    Can be overridden by the DEVWS_WS_SYNC_LABEL_KEY environment variable.
    """
    return os.environ.get("DEVWS_WS_SYNC_LABEL_KEY", "ws-sync")

def get_git_repo_info():
    """
    Extracts Git repository owner and name from the origin URL.
    Returns (owner, repo_name) or (None, None) if not a Git repo or origin not found.
    """
    try:
        # Check if current directory is a Git repository
        _run_command(['git', 'rev-parse', '--is-inside-work-tree'], capture_output=True)
    except subprocess.CalledProcessError:
        click.echo("❌ Not inside a Git repository.", err=True)
        return None, None

    try:
        origin_url = _run_command(['git', 'config', '--get', 'remote.origin.url'], capture_output=True).stdout.strip()
    except subprocess.CalledProcessError:
        click.echo("❌ Git origin URL not found.", err=True)
        return None, None

    # Regex to parse common Git URL formats (HTTPS and SSH)
    # e.g., https://github.com/owner/repo.git or git@github.com:owner/repo.git
    match = re.search(r'(?:github\.com|gitlab\.com|bitbucket\.org)[/:]([^/]+)/([^/.]+)(?:\.git)?', origin_url)
    if match:
        owner = match.group(1)
        repo_name = match.group(2)
        return owner, repo_name
    else:
        click.echo(f"❌ Could not parse owner and repo name from Git origin URL: {origin_url}", err=True)
        return None, None

def get_gcs_profile_config(profile_name='default', silent=False, debug=False):
    """
    Retrieves project_id and bucket_name from global config.
    Returns (project_id, bucket_name) or (None, None) if not found.
    """
    global_config, _ = _load_global_config(silent=silent, debug=debug)

    # Use top-level project_id and gcs_bucket settings
    project_id = global_config.get('project_id')
    bucket_name = global_config.get('gcs_bucket')

    return project_id, bucket_name

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

    try:
        if gcs_object_path.endswith('/'):
            list_output = gcs_manager.gcs_ls(gcs_object_path, recursive=False)
            if list_output:
                 return { "status": "Present", "type": "Directory", "metadata": {} }
            else:
                try:
                    gcs_manager.gcs_stat(gcs_object_path)
                    return { "status": "Present", "type": "Directory", "metadata": {} }
                except subprocess.CalledProcessError:
                    pass
        else:
            list_output = gcs_manager.gcs_ls(f"{gcs_object_path}/", recursive=False)
            if list_output:
                is_directory = False
                for item in list_output:
                    if item.endswith('/') or len(list_output) > 1:
                        is_directory = True
                        break
                if is_directory:
                    return { "status": "Present", "type": "Directory", "metadata": {} }
    except Exception:
        pass

    try:
        obj_stats = gcs_manager.gcs_stat(gcs_object_path)
        if obj_stats:
            status = "Present"
            file_type = "File"
            if 'Update time' in obj_stats:
                metadata['last_modified_timestamp'] = obj_stats['Update time']
            if 'Hash (md5)' in obj_stats:
                metadata['md5_hash'] = obj_stats['Hash (md5)']
            return { "status": status, "type": file_type, "metadata": metadata }
    except Exception as e:
        click.echo(f"DEBUG: gcs_stat failed for {gcs_object_path}: {e}", err=True)
        pass

    return { "status": "Not Present", "type": "N/A", "metadata": {} }


def _get_local_file_status(local_file_path):
    """
    Determines the existence, type (file/directory), and relevant metadata
    of a given path on the local filesystem.
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
                mtime = os.path.getmtime(local_file_path)
                metadata['last_modified_timestamp'] = datetime.fromtimestamp(mtime).isoformat()
                metadata['md5_hash'] = _get_file_hash(local_file_path, algorithm='md5')
            except Exception as e:
                click.echo(f"❌ Error getting local file metadata for {local_file_path}: {e}", err=True)
        
    return { "status": status, "type": file_type, "metadata": metadata }

def _generate_ascii_table(data):
    """
    Generates a human-readable ASCII table from a list of dictionaries.
    """
    if not data:
        return "No data to display."

    columns = [(key, key.replace('_', ' ').title()) for key in data[0].keys()]
    
    column_widths = {}
    for col_key, col_header in columns:
        column_widths[col_key] = len(col_header)
        for row in data:
            value_len = len(str(row.get(col_key, '')))
            if value_len > column_widths[col_key]:
                column_widths[col_key] = value_len
    
    headers = [col_header for _, col_header in columns]
    header_line = " | ".join(headers[i].ljust(column_widths[columns[i][0]]) for i in range(len(columns)))
    
    separator_line = "-+-".join("-" * column_widths[col_key] for col_key, _ in columns)

    table_rows = [header_line, separator_line]

    for row in data:
        row_values = []
        for key, _ in columns:
            row_values.append(str(row.get(key, '')).ljust(column_widths[key]))
        table_rows.append(" | ".join(row_values))

    return "\n".join(table_rows)
