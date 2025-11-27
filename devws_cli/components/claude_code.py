import click
import os
from devws_cli.utils import _log_step, _run_command

def setup(config, dry_run=False):
    """
    Manages the Claude Code CLI installation.
    """
    if not config.get("enabled", True):
        _log_step("Claude Code Setup", "DISABLED")
        return

    click.echo("\nClaude Code Setup")
    
    # 1. Check if already installed (VERIFIED)
    if _run_command(['which', 'claude'], capture_output=True, check=False).returncode == 0:
         _log_step("Claude Code Setup", "VERIFIED", "Claude Code is already installed.")
         return

    # 2. If not installed, check dry_run (READY)
    if dry_run:
        _log_step("Claude Code Setup", "READY", "Would install Claude Code CLI.")
        return

    # 3. Perform Installation (COMPLETED/FAILED)
    try:
        click.echo("Installing Claude Code CLI...")
        _run_command(['npm', 'install', '-g', '@anthropic-ai/claude-code'])
        _log_step("Claude Code Setup", "COMPLETED", "Installed Claude Code CLI.")
        
    except Exception as e:
        _log_step("Claude Code Setup", "FAIL", f"Installation failed: {e}")

    click.echo("-" * 60)
