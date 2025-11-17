import click
import os
from devws_cli.utils import _log_step, _run_command

def setup(config):
    """
    Manages the Gemini CLI installation.
    """
    if not config.get("enabled", True):
        _log_step("Gemini CLI Installation", "DISABLED")
        return

    click.echo("\nStep 4: Gemini CLI Installation")

    if not _run_command(['which', 'gemini'], capture_output=True, check=False).returncode == 0:
        click.echo("Installing Gemini CLI...")
        try:
            _run_command(['sudo', 'npm', 'install', '-g', '@google/gemini-cli'])
            _log_step("Gemini CLI Installation", "COMPLETED")
            if _run_command(['which', 'gemini'], capture_output=True, check=False).returncode == 0:
                _log_step("Gemini CLI Validation", "COMPLETED")
            else:
                _log_step("Gemini CLI Validation", "FAIL", "Gemini CLI command not found after installation.")
        except Exception:
            _log_step("Gemini CLI Installation", "FAIL")
    else:
        click.echo("Gemini CLI is already installed and accessible.")
        _log_step("Gemini CLI Installation", "VERIFIED")
        _log_step("Gemini CLI Validation", "VERIFIED")
    click.echo("-" * 60)
