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

def convert_md_to_html(md_file: Path, output_html_path: Path):
    """Converts a Markdown file to HTML using pandoc."""
    pandoc_command = ["pandoc", "-f", "markdown", "-t", "html", "-s", str(md_file), "-o", str(output_html_path)]
    try:
        print(f"✓ Converted '{md_file}' to '{output_html_path}'")
        subprocess.run(pandoc_command, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR: Failed to convert with pandoc. Is 'pandoc' installed?", file=sys.stderr)
        print(f"  Details: {e.stderr if hasattr(e, 'stderr') else e}", file=sys.stderr)
        sys.exit(1)

def open_file_in_chromeos_browser(file_path: Path):
    """
    Opens a local HTML file in the ChromeOS host browser using the 'google-chrome' command.
    It runs in the background to not block the terminal.
    """
    try:
        print(f"Opening '{file_path.name}' in ChromeOS browser (in background)...")
        # Use subprocess.Popen to run in the background
        subprocess.Popen(["google-chrome", str(file_path.resolve())])
        print("✓ Success! The file should be open in your ChromeOS browser.")
    except (FileNotFoundError) as e:
        print(f"ERROR: 'google-chrome' command not found. Is Chrome installed?", file=sys.stderr)
        print(f"  Details: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to open file with google-chrome.", file=sys.stderr)
        print(f"  Details: {e}", file=sys.stderr)
        sys.exit(1)