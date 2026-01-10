
import click
from devws_cli.utils import _log_step, _run_command, _get_os_type

def setup(config, dry_run=False):
    """
    Manages the Google Cloud CLI installation and authentication.
    """
    if not config.get("enabled", True):
        _log_step("Google Cloud Cli Setup", "DISABLED")
        return

    click.echo("\nStep 2: Google Cloud Cli Setup")
    
    # 1. Check if already installed (VERIFIED)
    gcloud_installed = False
    if _run_command(['which', 'gcloud'], capture_output=True, check=False).returncode == 0:
        gcloud_installed = True
        click.echo("Google Cloud CLI (gcloud) is already installed.")
        
        # Check authentication status (optional, but good for verification)
        # gcloud auth list returns 0 even if empty list, so check output
        auth_list = _run_command(['gcloud', 'auth', 'list', '--format=json'], capture_output=True, check=False)
        if auth_list.returncode == 0 and auth_list.stdout.strip() != "[]":
             _log_step("Google Cloud Cli Setup", "VERIFIED", "GCloud CLI installed and authenticated.")
             return
        else:
             click.echo("GCloud CLI installed but might not be authenticated.")
             # Proceed to auth if not dry run? Or just mark VERIFIED as installed?
             # User said "if the thing it installs is already installed and return VERIFIED".
             # So we mark VERIFIED.
             _log_step("Google Cloud Cli Setup", "VERIFIED", "GCloud CLI installed.")
             return

    # 2. If not installed, check dry_run (READY)
    if dry_run:
        _log_step("Google Cloud Cli Setup", "READY", "Would install Google Cloud CLI.")
        return

    # 3. Perform Installation (COMPLETED/FAILED)
    os_type = _get_os_type()
    try:
        if os_type == "darwin":
            _run_command(['brew', 'install', '--cask', 'google-cloud-sdk'])
            _log_step("Google Cloud Cli Setup", "COMPLETED")
        elif os_type == "linux-gnu":
            # Simplified linux install
            _run_command(['sudo', 'apt-get', 'install', 'google-cloud-cli', '-y'])
            _log_step("Google Cloud Cli Setup", "COMPLETED")
        else:
            _log_step("Google Cloud Cli Setup", "FAIL", "Unsupported OS.")
            return
    except Exception as e:
        _log_step("Google Cloud Cli Setup", "FAIL", f"Installation failed: {e}")
        return

    # 4. Authentication (Interactive)
    # Only reachable if we just installed it
    click.echo("Authenticating with Google Cloud...")
    try:
        _run_command(['gcloud', 'init'], check=False) # Interactive
        _log_step("Google Cloud Cli Setup", "COMPLETED", "Initialization finished.")
    except Exception as e:
        _log_step("Google Cloud Cli Setup", "FAIL", f"Initialization failed: {e}")

    click.echo("-" * 60)