import click
import os
from devws_cli.utils import _log_step, _run_command, _get_os_type

def setup(config, dry_run=False):
    """
    Manages the Node.js installation.
    """
    if not config.get("enabled", True):
        _log_step("Nodejs Installation", "DISABLED")
        return

    click.echo("\nStep 6: Node.js Installation")
    nodejs_min_version = config.get("min_version", "20")
    
    nodejs_installed = False
    
    # 1. Check if already installed (VERIFIED)
    if _run_command(['which', 'node'], capture_output=True, check=False).returncode == 0:
        try:
            current_version_str = _run_command(['node', '-v'], capture_output=True).stdout.strip()
            # node -v returns v20.x.x, strip 'v'
            if current_version_str.startswith('v'):
                current_version_str = current_version_str[1:]
            
            current_major = int(current_version_str.split('.')[0])
            required_major = int(nodejs_min_version)

            if current_major >= required_major:
                nodejs_installed = True
                click.echo(f"Node.js {current_version_str} is already installed (meets minimum requirement {nodejs_min_version}).")
                _log_step("Nodejs Installation", "VERIFIED")
                return # Already verified, exit
            else:
                click.echo(f"Node.js {current_version_str} is too old (minimum {nodejs_min_version}). Update required.")
        except Exception:
            click.echo("Error checking Node.js version. Re-installation might be needed.")

    # 2. If not installed, check dry_run (READY)
    if dry_run:
        _log_step("Nodejs Installation", "READY", f"Would install Node.js {nodejs_min_version}+")
        return

    # 3. Perform Installation (COMPLETED/FAILED)
    os_type = _get_os_type()
    if os_type == "darwin":
        try:
            _run_command(['brew', 'install', 'node'])
            _log_step("Nodejs Installation", "COMPLETED")
        except Exception as e:
            _log_step("Nodejs Installation", "FAIL", f"Installation failed: {e}")
    elif os_type == "linux-gnu":
        try:
            # Using nodesource for newer node versions
            _run_command(['curl', '-fsSL', f'https://deb.nodesource.com/setup_{nodejs_min_version}.x', '|', 'sudo', '-E', 'bash', '-'], shell=True)
            _run_command(['sudo', 'apt-get', 'install', '-y', 'nodejs'])
            _log_step("Nodejs Installation", "COMPLETED")
        except Exception as e:
            _log_step("Nodejs Installation", "FAIL", f"Installation failed: {e}")
    else:
        _log_step("Nodejs Installation", "FAIL", "Unsupported OS for automatic Node.js installation.")
    click.echo("-" * 60)
