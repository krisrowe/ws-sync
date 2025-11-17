import click
from devws_cli.utils import _log_step, _run_command

def setup(config):
    """
    Manages the Cursor Agent installation.
    """
    if not config.get("enabled", True):
        _log_step("Cursor Agent Installation", "DISABLED")
        return

    click.echo("\nStep 3: Cursor Agent Installation")

    if not _run_command(['which', 'cursor-agent'], capture_output=True, check=False).returncode == 0:
        click.echo("Installing Cursor agent...")
        try:
            _run_command(['bash', '-c', 'curl https://cursor.com/install -fsSL | bash'])
            _log_step("Cursor Agent Installation", "COMPLETED")
        except Exception:
            _log_step("Cursor Agent Installation", "FAIL")
    else:
        click.echo("Cursor agent is already installed.")
        _log_step("Cursor Agent Installation", "VERIFIED")
    click.echo("-" * 60)
