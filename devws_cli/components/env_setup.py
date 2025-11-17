import click
import os
from devws_cli.utils import _log_step, _update_bashrc, _validate_secrets_manager_backup

def setup(config):
    """
    Manages the Environment Configuration setup.
    """
    if not config.get("enabled", True):
        _log_step("Environment Configuration Setup", "DISABLED")
        return

    click.echo("\nStep 7: Environment Configuration Setup")
    ENV_FILE = os.path.expanduser("~/.env")

    if os.path.exists(ENV_FILE):
        click.echo(f"Found environment file at {ENV_FILE}")
        _log_step("Environment File Detection", "VERIFIED")
    else:
        click.echo(f"No environment file found at {ENV_FILE}")
        _log_step("Environment File Detection", "FAIL", "Create ~/.env file with your API keys.")

    bashrc_snippet = f"""
# Load environment file
if [ -f "{ENV_FILE}" ]; then
    echo "Loading environment from {ENV_FILE}"
    source "{ENV_FILE}"
fi
"""
    if _update_bashrc(bashrc_snippet, "Load environment file"):
        _log_step("Shell Startup Integration", "COMPLETED")
    else:
        _log_step("Shell Startup Integration", "VERIFIED")

    # Validate secrets backup
    _validate_secrets_manager_backup(config) # Pass the component config, which includes project_id
    click.echo("-" * 60)
