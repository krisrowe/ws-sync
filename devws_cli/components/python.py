import click
import os
import sys
from devws_cli.utils import _log_step, _run_command, _get_os_type

def setup(config, dry_run=False):
    """
    Manages the Python installation.
    """
    if not config.get("enabled", True):
        _log_step("Python Installation", "DISABLED")
        return

    click.echo("\nStep 5: Python Installation")
    python_min_version = config.get("min_version", "3.9")
    
    python_installed = False
    
    # 1. Check if already installed (VERIFIED)
    if _run_command(['which', 'python3'], capture_output=True, check=False).returncode == 0:
        try:
            current_version_str = _run_command(['python3', '-c', "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], capture_output=True).stdout.strip()
            current_major, current_minor = map(int, current_version_str.split('.'))
            required_major, required_minor = map(int, python_min_version.split('.'))

            if current_major > required_major or (current_major == required_major and current_minor >= required_minor):
                python_installed = True
                click.echo(f"Python {current_version_str} is already installed (meets minimum requirement {python_min_version}).")
                _log_step("Python Installation", "VERIFIED")
                return # Already verified, exit
            else:
                click.echo(f"Python {current_version_str} is too old (minimum {python_min_version}). Update required.")
        except Exception:
            click.echo("Error checking Python version. Re-installation might be needed.")

    # 2. If not installed, check dry_run (READY)
    if dry_run:
        _log_step("Python Installation", "READY", f"Would install Python {python_min_version}+")
        return

    # 3. Perform Installation (COMPLETED/FAILED)
    os_type = _get_os_type()
    if os_type == "darwin":
        try:
            # Re-calculate required version for install command
            required_major, required_minor = map(int, python_min_version.split('.'))
            _run_command(['brew', 'install', f'python@{required_major}.{required_minor}'])
            _log_step("Python Installation", "COMPLETED")
        except Exception as e:
            _log_step("Python Installation", "FAIL", f"Installation failed: {e}")
    elif os_type == "linux-gnu":
        try:
            _run_command(['sudo', 'apt-get', 'update'])
            _run_command(['sudo', 'apt-get', 'install', 'python3', 'python3-pip', '-y'])
            _log_step("Python Installation", "COMPLETED")
        except Exception as e:
            _log_step("Python Installation", "FAIL", f"Installation failed: {e}")
    else:
        _log_step("Python Installation", "FAIL", "Unsupported OS for automatic Python installation.")
    click.echo("-" * 60)
