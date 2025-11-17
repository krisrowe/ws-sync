import click
import os
from devws_cli.utils import _log_step, _run_command, _get_os_type

def setup(config):
    """
    Manages the Node.js installation.
    """
    if not config.get("enabled", True):
        _log_step("Node.js Setup", "DISABLED")
        return

    click.echo("\nStep 6: Node.js Setup")
    nodejs_min_version = config.get("min_version", "20")
    
    node_installed = False
    node_version_ok = False

    # Check if Node.js is available and meets version requirements
    which_node_result = _run_command(['which', 'node'], capture_output=True, check=False, env=os.environ)
    if which_node_result.returncode == 0:
        try:
            current_version_str = _run_command(['node', '-v'], capture_output=True, env=os.environ).stdout.strip().lstrip('v')
            current_major = int(current_version_str.split('.')[0])
            required_major = int(nodejs_min_version)

            if current_major >= required_major:
                node_installed = True
                node_version_ok = True
                _log_step("Node.js Installation", "VERIFIED", f"Node.js v{current_version_str} is already installed (meets minimum requirement v{nodejs_min_version}).")
            else:
                _log_step("Node.js Installation", "PARTIAL", f"Node.js v{current_version_str} is too old (minimum v{nodejs_min_version}). Please update manually.")
        except Exception as e:
            _log_step("Node.js Installation", "FAIL", f"Error checking Node.js version: {e}. Please install/update manually.")
    else:
        _log_step("Node.js Installation", "FAIL", f"Node.js not found. Please install Node.js v{nodejs_min_version} or later manually.")
    click.echo("-" * 60)
