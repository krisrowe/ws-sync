import click
import os
import glob # For file pattern matching
from devws_cli.utils import _run_command

@click.group()
def clean_group(): # Renamed to avoid conflict with 'clean' command
    """
    Manages cleanup operations.
    """
    pass

@clean_group.command(name="clean") # Explicitly name the command 'clean'
def clean_command(): # Renamed function to avoid conflict
    """
    Cleans up temporary files.
    """
    click.echo("ℹ️ Cleaning up temporary files...")
    deleted_count = 0
    # Find and delete files matching *.backup.*
    # os.walk works recursively, so using it to search the current directory and subdirectories
    for root, _, files in os.walk('.'):
        for file in files:
            if ".backup." in file:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    click.echo(f"🗑️ Deleted: {file_path}")
                    deleted_count += 1
                except OSError as e:
                    click.echo(f"❌ Error deleting {file_path}: {e}", err=True)
    
    if deleted_count == 0:
        click.echo("✅ No temporary files found to clean.")
    else:
        click.echo(f"✅ Cleaned up {deleted_count} temporary files.")
    click.echo("Clean complete.")
