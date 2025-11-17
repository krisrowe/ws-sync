import click
from devws_cli.utils import _log_step, _run_command, _get_os_type

def setup(config):
    """
    Manages the Google Cloud CLI installation.
    """
    if not config.get("enabled", True):
        _log_step("Google Cloud CLI Installation", "DISABLED")
        return

    click.echo("\nStep 2: Google Cloud CLI Installation")

    if not _run_command(['which', 'gcloud'], capture_output=True, check=False).returncode == 0:
            click.echo("Google Cloud CLI not found. Installing gcloud cli...")
            os_type = _get_os_type()
            if os_type == "darwin":
                try:
                    _run_command(['brew', 'install', '--cask', 'google-cloud-sdk'])
                    _log_step("Google Cloud CLI Installation", "COMPLETED")
                except Exception:
                    _log_step("Google Cloud CLI Installation", "FAIL", "Please install Google Cloud CLI manually: https://cloud.google.com/sdk/docs/install")
            elif os_type == "linux-gnu":
                try:
                    _run_command(['sudo', 'apt-get', 'update'])
                    _run_command(['sudo', 'apt-get', 'install', 'google-cloud-cli', '-y'])
                    _log_step("Google Cloud CLI Installation", "COMPLETED")
                except Exception:
                    _log_step("Google Cloud CLI Installation", "FAIL", "Please install Google Cloud CLI manually: https://cloud.google.com/sdk/docs/install")
            else:
                _log_step("Google Cloud CLI Installation", "FAIL", "Unsupported OS for automatic Google Cloud CLI installation. Install manually.")
    else:
        click.echo("Google Cloud CLI is already installed.")
        _log_step("Google Cloud CLI Installation", "VERIFIED")
    click.echo("-