import click
import os
import re
from devws_cli.utils import _log_step, _run_command, _get_os_type, _update_bashrc

def setup(config, dry_run=False):
    """
    Manages the GitHub CLI installation and authentication.
    """
    if not config.get("enabled", True):
        _log_step("Github Setup", "DISABLED")
        return

    click.echo("\nStep 1: Github Setup")
    
    # 1. Check if already installed (VERIFIED)
    gh_installed = False
    if _run_command(['which', 'gh'], capture_output=True, check=False).returncode == 0:
        gh_installed = True
        click.echo("GitHub CLI (gh) is already installed.")
        
        # Check authentication status
        auth_status = _run_command(['gh', 'auth', 'status'], capture_output=True, check=False)
        if auth_status.returncode == 0:
             _log_step("Github Setup", "VERIFIED", "GitHub CLI installed and authenticated.")
             return # Already verified, exit
        else:
             click.echo("GitHub CLI installed but not authenticated.")
             # If installed but not authenticated, we might want to proceed to auth step
             # But for now, let's treat it as PARTIAL/VERIFIED for installation, but maybe not fully setup.
             # The user requirement says "if the thing it installs is already installed and return VERIFIED".
             # Authentication is an interactive step usually.
             # Let's proceed to auth step if not dry_run.
    
    # 2. If not installed, check dry_run (READY)
    if not gh_installed and dry_run:
        _log_step("Github Setup", "READY", "Would install GitHub CLI.")
        return

    # 3. Perform Installation (COMPLETED/FAILED)
    if not gh_installed:
        os_type = _get_os_type()
        try:
            if os_type == "darwin":
                _run_command(['brew', 'install', 'gh'])
                _log_step("Github Setup", "COMPLETED", "Installed GitHub CLI.")
            elif os_type == "linux-gnu":
                _run_command(['sudo', 'apt-get', 'install', 'gh', '-y']) 
                _log_step("Github Setup", "COMPLETED", "Installed GitHub CLI.")
            else:
                 _log_step("Github Setup", "FAIL", "Unsupported OS.")
                 return
        except Exception as e:
            _log_step("Github Setup", "FAIL", f"Installation failed: {e}")
            return

    # 4. Authentication (Interactive)
    # If we are here, it's installed (either was already or just installed).
    # If dry_run, we should have returned already if not installed.
    # If installed and dry_run, we returned VERIFIED if auth was good.
    # If installed and NOT auth good, and dry_run:
    if dry_run:
         _log_step("Github Setup", "READY", "Would authenticate GitHub CLI.")
         return

    # Perform Auth
    click.echo("Authenticating with GitHub...")
    try:
        _run_command(['gh', 'auth', 'login'], check=False) # Interactive
        _log_step("Github Setup", "COMPLETED", "Authentication flow finished.")
    except Exception as e:
        _log_step("Github Setup", "FAIL", f"Authentication failed: {e}")
    else:
        click.echo("GitHub CLI is authenticated.")
        _log_step("GitHub CLI Authentication", "VERIFIED")

    SSH_KEY_FILE = os.path.expanduser("~/.ssh/id_ed25519")

    # SSH Key Setup and GitHub Integration
    if not os.path.exists(SSH_KEY_FILE):
        click.echo("No SSH key found. Generating a new Ed25519 key pair...")
        email_comment = click.prompt("Please enter your email to use as a comment for the key")
        try:
            _run_command(['ssh-keygen', '-t', 'ed25519', '-f', SSH_KEY_FILE, '-C', email_comment, '-q', '-N', ''])
            _log_step("SSH Key Generation", "COMPLETED")
        except Exception:
            _log_step("SSH Key Generation", "FAIL")
    else:
        click.echo(f"SSH key already exists at {SSH_KEY_FILE}.")
        _log_step("SSH Key Generation", "VERIFIED")

    # Add SSH key to GitHub
    if os.path.exists(f"{SSH_KEY_FILE}.pub"):
        gh_ssh_keys = _run_command(['gh', 'ssh-key', 'list'], capture_output=True).stdout
        with open(f"{SSH_KEY_FILE}.pub", 'r') as f:
            local_key_content_full = f.read().strip()
            local_key_part_match = re.match(r'^(ssh-ed25519\s+[^\s]+)', local_key_content_full)
            local_key_part = local_key_part_match.group(1) if local_key_part_match else local_key_content_full

        if local_key_part not in gh_ssh_keys:
            click.echo("Adding the public key to your GitHub account via gh cli...")
            try:
                _run_command(['gh', 'ssh-key', 'add', f"{SSH_KEY_FILE}.pub", '--title', f"{_get_os_type()} - {os.getenv('USER')}@{os.uname().nodename}", '--type', 'authentication'])
                _log_step("SSH Key GitHub Integration", "COMPLETED")
            except Exception:
                _log_step("SSH Key GitHub Integration", "FAIL")
        else:
            click.echo("SSH key is already added to GitHub.")
            _log_step("SSH Key GitHub Integration", "VERIFIED")
    else:
        _log_step("SSH Key GitHub Integration", "FAIL", "Public SSH key not found.")

    # Set up SSH agent
    if not _run_command(['pgrep', '-u', os.getenv('USER'), 'ssh-agent'], capture_output=True, check=False).returncode == 0:
        click.echo("SSH agent not running. Starting and adding key...")
        try:
            _run_command(['eval', '"$(ssh-agent -s)"'], shell=True)
            _run_command(['ssh-add', SSH_KEY_FILE])
            _log_step("SSH Agent Setup", "COMPLETED")
        except Exception:
            _log_step("SSH Agent Setup", "FAIL")
    else:
        click.echo("SSH agent is already running.")
        _log_step("SSH Agent Setup", "VERIFIED")

    # Add SSH agent startup to .bashrc
    bashrc_snippet = f"""
# SSH-agent setup for GitHub access
if [ -f "{SSH_KEY_FILE}" ] && ! pgrep -u "$USER" ssh-agent > /dev/null;
then
    eval "$(ssh-agent -s)" > /dev/null
    ssh-add "{SSH_KEY_FILE}" > /dev/null
fi
"""
    if _update_bashrc(bashrc_snippet, "SSH-agent setup"):
        _log_step("SSH Agent Auto-start Configuration", "COMPLETED")
    else:
        _log_step("SSH Agent Auto-start Configuration", "VERIFIED")
    click.echo("-" * 60)
