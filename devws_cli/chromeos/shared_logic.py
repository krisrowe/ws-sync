# devws_cli/chromeos/shared_logic.py
import subprocess
import sys
import shutil # For shutil.which
from pathlib import Path

# This script provides shared utility logic for ChromeOS integration.

def check_pandoc_installed():
    """Checks if pandoc is installed and accessible in the PATH."""
    return shutil.which("pandoc") is not None

def check_google_chrome_installed():
    """Checks if google-chrome is installed and accessible in the PATH."""
    return shutil.which("google-chrome") is not None

def open_file_in_chromeos_browser(file_path: Path):
    """
    Opens a file in the ChromeOS host browser using the 'xdg-open' command.
    """
    try:
        print(f"Attempting to open '{file_path.name}' in ChromeOS browser...")
        subprocess.run(["xdg-open", str(file_path.resolve())], check=True)
        print("✓ Success! The file should be open in your ChromeOS browser.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR: Failed to open file with xdg-open.", file=sys.stderr)
        print(f"  Details: {e.stderr if hasattr(e, 'stderr') else e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to open file.", file=sys.stderr)
        print(f"  Details: {e}", file=sys.stderr)
        sys.exit(1)
