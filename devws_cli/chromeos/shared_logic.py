# devws_cli/chromeos/shared_logic.py
import subprocess
import sys
import shutil # For shutil.which
import os # For os.devnull
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
    Opens a file in the ChromeOS host browser using the 'google-chrome' command,
    running it as a detached background process to not block the terminal.
    """
    try:
        print(f"Attempting to open '{file_path.name}' in ChromeOS browser (as detached background process)...")
        
        # Use subprocess.Popen with detached process, and redirect stdio to /dev/null
        # This prevents the parent process from waiting for the child, and avoids TTY issues.
        subprocess.Popen(
            ["google-chrome", str(file_path.resolve())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True, # Close all file descriptors when child exits
            start_new_session=True # Detach from current process group
        )
        print("✓ Success! The file should be open in your ChromeOS browser.")
    except FileNotFoundError:
        print(f"ERROR: 'google-chrome' command not found. Is Chrome installed in the Linux container?", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to open file with google-chrome.", file=sys.stderr)
        print(f"  Details: {e}", file=sys.stderr)
        sys.exit(1)
