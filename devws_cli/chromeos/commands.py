# devws_cli/chromeos/commands.py
import json
import subprocess
import sys
import shutil
from pathlib import Path

import click

from devws_cli.chromeos.shared_logic import check_pandoc_installed, check_google_chrome_installed, open_file_in_chromeos_browser

PROJECT_GEMINI_MD = Path.cwd() / "GEMINI.md"

@click.group()
def chrome():
    """Commands for ChromeOS integration."""
    pass

@chrome.command("init")
def init_chromeos():
    """
    Idempotently sets up ChromeOS integration for Gemini CLI.

    - Ensures pandoc and google-chrome are installed (provides guidance if not).
    - Updates the project's GEMINI.md with usage instructions.
    """
    click.echo("\n--- Running ChromeOS Integration Setup ---")

    # 1. Check for tool installation
    if not shutil.which("jq"):
        click.echo("ERROR: 'jq' is not installed. Please install it: sudo apt install -y jq", err=True)
        sys.exit(1)
    if not check_pandoc_installed():
        click.echo("WARNING: 'pandoc' is not installed. Please install it: sudo apt install -y pandoc", err=True)
    if not check_google_chrome_installed():
        click.echo("WARNING: 'google-chrome' is not installed. Ensure Chrome is correctly set up for Crostini.", err=True)

    # 2. Update project's GEMINI.md with usage instructions
    click.echo("\nUpdating project's GEMINI.md with usage instructions...")
    gemini_md_content = ""
    if PROJECT_GEMINI_MD.exists():
        gemini_md_content = PROJECT_GEMINI_MD.read_text()

    new_instructions = f"""
## Previewing Markdown Files (ChromeOS)

This project includes a workflow for previewing Markdown (`.md`) files directly in your ChromeOS browser.

### One-Time Setup

Before using the preview functionality, ensure you've run the setup command:

```bash
devws chrome init
```
This command automatically checks for necessary tools like `pandoc` and `google-chrome`.

### Usage

Once set up, you can preview any Markdown file in your project with the `devws chrome open` command.

**Syntax:**
```bash
devws chrome open <path/to/your-file.md>
```

**Example:**
To preview the `apigee_feedback_breakdown.md` file:
```bash
devws chrome open apigee_feedback_breakdown.md
```
This will attempt to open the Markdown file directly in your ChromeOS browser.
"""

    if new_instructions not in gemini_md_content:
        with open(PROJECT_GEMINI_MD, "a") as f:
            f.write("\n" + new_instructions)
        click.echo(f"✓ Added preview instructions to '{PROJECT_GEMINI_MD}'")
    else:
        click.echo(f"  Preview instructions already present in '{PROJECT_GEMINI_MD}'.")

    click.echo("\n--- ChromeOS Integration Setup Complete ---")


@chrome.command("open")
@click.argument("markdown_file", type=click.Path(exists=True, path_type=Path))
def open_in_browser(markdown_file: Path):
    """
    Attempts to open a Markdown file directly in the ChromeOS browser.
    """
    click.echo(f"\n--- Opening '{markdown_file}' in ChromeOS Browser ---")

    # Open the markdown file directly in the browser
    open_file_in_chromeos_browser(markdown_file)

    click.echo("\n--- ChromeOS Browser Opening Complete ---")
