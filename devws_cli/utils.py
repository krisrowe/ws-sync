import subprocess
import click
import os
import sys
import hashlib
import re # Import re for regular expressions
import yaml # Import yaml for global config

# Global status tracking
STEP_STATUS = {}
STEP_COUNT = 0

# Global Configuration Paths
GLOBAL_DEVWS_CONFIG_DIR = os.path.expanduser("~/.config/devws")
GLOBAL_DEVWS_CONFIG_FILE = os.path.join(GLOBAL_DEVWS_CONFIG_DIR, "config.yaml")

def _run_command(command, check=True, capture_output=False, shell=False, cwd=None, env=None, debug=False):
    """
    Wrapper for subprocess.run to execute shell commands.
    
    Args:
        debug: If True, shows error messages when commands fail
    """
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

def _log_step(step_name, status, message=None):
    """
    Logs the status of a setup step.
    """
    global STEP_COUNT
    STEP_COUNT += 1
    STEP_STATUS[step_name] = status

    status_emoji = {
        "PASS": "✅",
        "COMPLETED": "✅",
        "VERIFIED": "✅",
        "SKIP": "⏭️",
        "DISABLED": "🚫",
        "PARTIAL": "⚠️",
        "FAIL": "❌",
    }.get(status, "❓")

    status_text = {
        "PASS": "PASSED",
        "COMPLETED": "COMPLETED (just finished)",
        "VERIFIED": "VERIFIED (already done)",
        "SKIP": "SKIPPED (not applicable)",
        "DISABLED": "DISABLED (configuration)",
        "PARTIAL": "PARTIAL (needs attention)",
        "FAIL": "FAILED",
    }.get(status, "UNKNOWN")

    click.echo(f"{status_emoji} {step_name} - {status_text}")
    if message:
        click.echo(f"  → {message}")

def _print_final_report():
    """
    Prints the final setup report.
    """
    click.echo("\n" + "=" * 60)
    click.echo("SETUP REPORT".center(60))
    click.echo("=" * 60)
    click.echo(f"{ 'STEP':<40} {'STATUS':<10}")
    click.echo("-" * 60)

    for step, status in STEP_STATUS.items():
        status_display = {
            "PASS": "✅ PASS",
            "COMPLETED": "✅ COMPLETED",
            "VERIFIED": "✅ VERIFIED",
            "SKIP": "⏭️  SKIP",
            "DISABLED": "🚫 DISABLED",
            "PARTIAL": "⚠️  PARTIAL",
            "FAIL": "❌ FAIL",
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
            "github": {"enabled": True},
            "google_cloud_cli": {"enabled": True},
            "python": {"enabled": True, "min_version": "3.9"},
            "nodejs": {"enabled": True, "min_version": "20"},
            "cursor_agent": {"enabled": True},
            "gemini_cli": {"enabled": True},
            "env_setup": {"enabled": True},
            "proj_local_config_sync": {
                "enabled": True,
                "local_sync_candidates": ["*.env"],
                "bucket_name": "" # Default empty
            },
        },
        "project_id": "" # Default empty, now lowercase
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

def _update_bashrc(snippet, identifier):
    """
    Adds a snippet to ~/.bashrc if it's not already present, identified by a unique string.
    """
    bashrc_path = os.path.expanduser("~/.bashrc")
    try:
        with open(bashrc_path, 'r+') as f:
            content = f.read()
            if identifier not in content:
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
    Loads global devws configuration from ~/.config/devws/config.yaml or from WS_SYNC_CONFIG env var.
    Returns a dictionary of config values with defaults.
    
    Args:
        silent: If True, suppresses informational output
        debug: If True, shows debug output
    """
    config = {
        'local_sync_candidates': ['*.env'], # Default candidates
        'default_gcp_project_id': '', # Default empty. Used by secrets backup.
    }

    # Determine the actual global config file path, respecting WS_SYNC_CONFIG env var
    actual_global_config_file = os.environ.get("WS_SYNC_CONFIG", GLOBAL_DEVWS_CONFIG_FILE)
    if debug:
        click.echo(f"DEBUG: Using global config file: {actual_global_config_file}")

    if os.path.exists(actual_global_config_file):
        try:
            with open(actual_global_config_file, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    config.update(user_config)
        except yaml.YAMLError as e:
            click.echo(f"⚠️ Warning: Error parsing global config file {actual_global_config_file}: {e}", err=True)
    
    return config, actual_global_config_file

def _get_ws_sync_label_key():
    """
    Returns the label key used for GCS synchronization.
    Can be overridden by the DEVWS_WS_SYNC_LABEL_KEY environment variable.
    """
    return os.environ.get("DEVWS_WS_SYNC_LABEL_KEY", "ws-sync")
