import os
import zipfile
import datetime
import fnmatch
from pathlib import Path
import tempfile
import click

def create_home_backup(exclusions, inclusions, local_output_dir, gcs_manager, gcs_path, debug):
    """
    Creates a backup of the home directory, optionally uploading to GCS.

    Args:
        exclusions (list): Glob patterns to exclude.
        inclusions (list): Glob patterns to explicitly include.
        local_output_dir (str): Local directory to save the backup if GCS is not used.
        gcs_manager (GCSManager): Instance of GCSManager for GCS operations.
        gcs_path (str): The destination path in GCS.
        debug (bool): Flag for debug output.
    """
    home_dir = Path.home()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    backup_basename = f"home_{timestamp}.zip"

    # Determine if we are doing a local or GCS backup
    if gcs_manager:
        # For GCS, create backup in a temporary directory first
        temp_dir = tempfile.TemporaryDirectory()
        local_backup_path = Path(temp_dir.name) / backup_basename
        click.echo(f"Creating temporary local backup at {local_backup_path}...")
    else:
        # For local backup, use the specified output directory
        backup_dir = Path(local_output_dir)
        backup_dir.mkdir(exist_ok=True)
        local_backup_path = backup_dir / backup_basename
        click.echo(f"Creating backup archive at {local_backup_path}...")

    # --- Create the zip file ---
    try:
        with zipfile.ZipFile(local_backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(home_dir, topdown=True):
                # Prune directories from traversal
                dirs[:] = [d for d in dirs if not is_excluded(Path(root) / d, home_dir, exclusions, inclusions, debug)]
                
                for file in files:
                    file_path = Path(root) / file
                    if not is_excluded(file_path, home_dir, exclusions, inclusions, debug):
                        relative_path = file_path.relative_to(home_dir)
                        zipf.write(file_path, relative_path)
    except Exception as e:
        click.echo(f"❌ An error occurred during zip file creation: {e}", err=True)
        return

    filesize_kb = local_backup_path.stat().st_size // 1024
    click.echo(f"✅ Local backup created successfully. Size: {filesize_kb} KB")

    # --- Upload to GCS if configured ---
    if gcs_manager and gcs_path:
        gcs_full_path = os.path.join(gcs_path, backup_basename)
        click.echo(f"⬆️ Uploading to GCS at {gcs_full_path}...")
        try:
            if gcs_manager.gcs_cp(str(local_backup_path), gcs_full_path, debug=debug):
                click.echo(f"✅ Successfully uploaded backup to GCS.")
                final_location = gcs_full_path
            else:
                click.echo(f"❌ Failed to upload backup to GCS.", err=True)
                final_location = local_backup_path
        except Exception as e:
            click.echo(f"❌ An error occurred during GCS upload: {e}", err=True)
            final_location = local_backup_path
    else:
        final_location = local_backup_path

    # --- Cleanup ---
    if gcs_manager:
        temp_dir.cleanup()
        if debug:
            click.echo(f"DEBUG: Cleaned up temporary directory {temp_dir.name}")

    # --- Final Report ---
    click.echo("\n--- Backup Complete ---")
    click.echo(f"Final backup location: {final_location}")
    click.echo(f"Archive size: {filesize_kb} KB")


def is_excluded(path, base_dir, exclusions, inclusions, debug):
    """
    Checks if a path should be excluded from the backup.
    The logic is: a path is excluded if it matches an exclusion pattern, UNLESS
    it also matches a more specific inclusion pattern.
    """
    relative_path_str = str(path.relative_to(base_dir))

    # An item is NOT excluded if it matches an inclusion pattern.
    for pattern in inclusions:
        # Match against the path and parent directories
        if fnmatch.fnmatch(relative_path_str, pattern) or fnmatch.fnmatch(relative_path_str, pattern + '/**'):
            if debug:
                click.echo(f"DEBUG: Path '{relative_path_str}' matches inclusion pattern '{pattern}'. Including.")
            return False 

    # An item IS excluded if it matches an exclusion pattern.
    for pattern in exclusions:
        if fnmatch.fnmatch(relative_path_str, pattern) or fnmatch.fnmatch(relative_path_str, pattern + '/**'):
            if debug:
                click.echo(f"DEBUG: Path '{relative_path_str}' matches exclusion pattern '{pattern}'. EXCLUDING.")
            return True
            
    # If it matches neither, it is not excluded.
    return False
