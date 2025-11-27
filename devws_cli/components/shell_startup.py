import click
import os
from devws_cli.utils import _log_step, _update_bashrc

def setup(config, dry_run=False):
    """
    Ensures the user's .bashrc sources the devws startup script directly from its installation location.
    """
    if not config.get("enabled", True):
        _log_step("Shell Startup", "DISABLED", category="core")
        return

    # --- Step 1: Determine the absolute path to the startup.sh script ---
    # The script is located in the parent directory of this component file.
    try:
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'startup.sh'))
        if not os.path.exists(script_path):
            _log_step("Shell Startup", "FAIL", message=f"Could not find startup.sh at expected path: {script_path}", category="core")
            return
    except Exception as e:
        _log_step("Shell Startup", "FAIL", message=f"Error determining startup.sh path: {e}", category="core")
        return

    # --- Step 2: Ensure .bashrc sources the startup script ---
    bashrc_snippet = f"""
# Source the devws startup script for shell integration
if [ -s "{script_path}" ]; then
    \\. "{script_path}"
fi
"""
    identifier = "# Source the devws startup script"

    if _update_bashrc(bashrc_snippet, identifier, dry_run=dry_run):
        if dry_run:
            _log_step("Shell Startup", "READY", message="Would add sourcing line to ~/.bashrc.", category="core")
        else:
            _log_step("Shell Startup", "COMPLETED", message="Added sourcing line to ~/.bashrc.", category="core")
    else:
        _log_step("Shell Startup", "VERIFIED", message="Sourcing line already present in ~/.bashrc.", category="core")
