import click
import os
import re
from devws_cli.utils import _log_step, _run_command, _get_os_type, _update_bashrc

def setup(config):
    """
    Manages the GitHub CLI and SSH setup.
    """
    if not config.get("enabled", True):
        _log_step("GitHub Setup (CLI + SSH)", "DISABLED")
        return

    click.echo("\nStep 1: GitHub Setup (CLI + SSH)")

    # Install GitHub CLI
    if not _run_command(['which', 'gh'], capture_output=True, check=False).returncode == 0:
        click.echo("GitHub CLI not found. Installing gh cli...")
        os_type = _get_os_type()
        if os_type == "darwin":
            try:
                _run_command(['brew', 'install', 'gh'])
                _log_step("GitHub CLI Installation", "COMPLETED")
            except Exception:
                _log_step("GitHub CLI Installation", "FAIL", "Please install GitHub CLI manually: https://cli.github.com/")
        elif os_type == "linux-gnu":
            try:
                _run_command(['sudo', 'apt-get', 'update'])
                _run_command(['sudo', 'apt-get', 'install', 'gh', '-y'])
                _log_step("GitHub CLI Installation", "COMPLETED")
            except Exception:
                _log_step("GitHub CLI Installation", "FAIL", "Please install GitHub CLI manually: https://cli.github.com/")
        else:
            _log_step("GitHub CLI Installation", "FAIL", "Unsupported OS for automatic GitHub CLI installation. Install manually.")
    else:
        click.echo("GitHub CLI is already installed.")
        _log_step("GitHub CLI Installation", "VERIFIED")

    # Authenticate GitHub CLI
    if _run_command(['gh', 'auth', 'status'], capture_output=True, check=False).returncode != 0:
        click.echo("You are not authenticated with GitHub. Please log in now.")
        try:
            _run_command(['gh', 'auth', 'login'])
            _log_step("GitHub CLI Authentication", "COMPLETED")
        except Exception:
            _log_step("GitHub CLI Authentication", "FAIL")
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
