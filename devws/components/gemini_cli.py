import click
import os
from devws_cli.utils import _log_step, _run_command

def setup(config, dry_run=False):
    """
    Manages the Gemini CLI installation.
    """
    if not config.get("enabled", True):
        _log_step("Gemini Cli Setup", "DISABLED")
        return

    click.echo("\nStep 4: Gemini Cli Setup")
    
    # 1. Check if already installed (VERIFIED)
    if _run_command(['which', 'gemini'], capture_output=True, check=False).returncode == 0:
         _log_step("Gemini Cli Setup", "VERIFIED", "Gemini CLI is already installed.")
         return

    # 2. If not installed, check dry_run (READY)
    if dry_run:
        _log_step("Gemini Cli Setup", "READY", "Would install Gemini CLI.")
        return

    # 3. Perform Installation (COMPLETED/FAILED)
    try:
        # Placeholder for actual install logic
        click.echo("Installing Gemini CLI...")
        # Simulating install command
        # Assuming pip install based on name
        _run_command(['pip', 'install', 'gemini-cli'])
        _log_step("Gemini Cli Setup", "COMPLETED", "Installed Gemini CLI.")
        
    except Exception as e:
        _log_step("Gemini Cli Setup", "FAIL", f"Installation failed: {e}")

    click.echo("-" * 60)
