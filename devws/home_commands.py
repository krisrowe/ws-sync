import click
import os
import sys
import shutil
from devws_cli.backup import create_home_backup
from devws_cli.utils import (_load_global_config, get_gcs_profile_config, _get_local_file_status, 
                             _get_gcs_file_status, _generate_ascii_table)
from devws_cli.gcs_manager import GCSManager

@click.group()
def home():
    """Commands for managing the user's home directory."""
    pass

@home.command()
@click.option('--profile', default='default', help='The GCS profile to use for the backup.')
@click.option('--debug', is_flag=True, help='Show debug output.')
def backup(profile, debug):
    """
    Creates a backup of the home directory.
    If a GCS bucket is configured for the profile, the backup is uploaded there.
    Otherwise, it is saved locally to the configured 'output_dir'.
    """
    click.echo("ℹ️ Loading backup configuration...")
    
    config, _ = _load_global_config(debug=debug)
    backup_config = config.get('home_backup', {})

    exclusions = backup_config.get('exclusions', [])
    inclusions = backup_config.get('inclusions', [])
    output_dir_str = backup_config.get('output_dir', '~/backups')
    local_output_dir = os.path.expanduser(output_dir_str)

    # Check for GCS configuration
    gcs_manager = None
    gcs_backup_path = None
    _, bucket_name = get_gcs_profile_config(profile, silent=True, debug=debug)
    
    if bucket_name:
        click.echo(f"ℹ️ GCS bucket '{bucket_name}' found for profile '{profile}'. Backup will be uploaded to GCS.")
        gcs_manager = GCSManager(bucket_name, profile_name=profile)
        gcs_backup_path = gcs_manager.get_home_backups_gcs_path()
    else:
        click.echo(f"ℹ️ No GCS bucket configured for profile '{profile}'. Backup will be saved locally.")

    if not exclusions:
        click.echo("⚠️ No exclusions configured in 'home_backup' section of your config. The backup might be very large.", err=True)

    click.echo("Starting home directory backup...")
    create_home_backup(
        exclusions=exclusions, 
        inclusions=inclusions, 
        local_output_dir=local_output_dir,
        gcs_manager=gcs_manager,
        gcs_path=gcs_backup_path,
        debug=debug
    )

# --- Dotfiles Sub-Group ---

@home.group()
def dotfiles():
    """Manages the synchronization of specific dotfiles."""
    pass

@dotfiles.command(name="push")
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def push(profile, debug):
    """
    Pushes files and directories specified in 'user_home_sync' from local to GCS.
    """
    click.echo(f"ℹ️ Pushing dotfiles for profile '{profile}'...")

    _, bucket_name = get_gcs_profile_config(profile, silent=True, debug=debug)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    dotfiles_gcs_path = gcs_manager.get_dotfiles_gcs_path()

    config, _ = _load_global_config(debug=debug)
    user_home_sync_items = config.get('user_home_sync', [])

    if not user_home_sync_items:
        click.echo("ℹ️ No items configured for 'user_home_sync' in global config. Nothing to push.")
        sys.exit(0)

    for item in user_home_sync_items:
        local_relative_path = item.get('path')
        item_type = item.get('type')

        if not local_relative_path or not item_type:
            click.echo(f"⚠️ Skipping malformed user_home_sync item: {item}", err=True)
            continue

        local_full_path = os.path.join(os.path.expanduser("~"), local_relative_path)
        gcs_full_path = os.path.join(dotfiles_gcs_path, local_relative_path)

        if not os.path.exists(local_full_path):
            click.echo(f"⚠️ Local path '{local_full_path}' not found. Skipping '{local_relative_path}'.")
            continue
        
        click.echo(f"⬆️ Pushing '{local_full_path}' to '{gcs_full_path}'...")
        try:
            if gcs_manager.gcs_cp(local_full_path, gcs_full_path, recursive=(item_type == "directory"), debug=debug):
                click.echo(f"✅ Successfully pushed '{local_relative_path}'.")
            else:
                click.echo(f"❌ Failed to push '{local_relative_path}'.", err=True)
        except Exception as e:
            click.echo(f"❌ An error occurred pushing '{local_relative_path}': {e}", err=True)
            sys.exit(1)

@dotfiles.command(name="pull")
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--force', is_flag=True, help='Force overwrite local files if they exist.')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def pull(profile, force, debug):
    """
    Pulls files and directories specified in 'user_home_sync' from GCS to local.
    """
    click.echo(f"ℹ️ Pulling dotfiles for profile '{profile}'...")

    _, bucket_name = get_gcs_profile_config(profile, silent=True, debug=debug)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    dotfiles_gcs_path = gcs_manager.get_dotfiles_gcs_path()
    
    config, _ = _load_global_config(debug=debug)
    user_home_sync_items = config.get('user_home_sync', [])

    if not user_home_sync_items:
        click.echo("ℹ️ No items configured for 'user_home_sync' in global config. Nothing to pull.")
        sys.exit(0)

    for item in user_home_sync_items:
        local_relative_path = item.get('path')
        item_type = item.get('type')

        if not local_relative_path or not item_type:
            click.echo(f"⚠️ Skipping malformed user_home_sync item: {item}", err=True)
            continue

        local_full_path = os.path.join(os.path.expanduser("~"), local_relative_path)
        gcs_full_path = os.path.join(dotfiles_gcs_path, local_relative_path)

        if os.path.exists(local_full_path) and not force:
            click.echo(f"⚠️ Local path '{local_full_path}' already exists. Use --force to overwrite. Skipping.")
            continue
        
        os.makedirs(os.path.dirname(local_full_path), exist_ok=True)

        click.echo(f"⬇️ Pulling '{gcs_full_path}' to '{local_full_path}'...")
        try:
            if gcs_manager.gcs_cp(gcs_full_path, local_full_path, recursive=(item_type == "directory"), debug=debug):
                click.echo(f"✅ Successfully pulled '{local_relative_path}'.")
            else:
                click.echo(f"❌ Failed to pull '{local_relative_path}'.", err=True)
        except Exception as e:
            click.echo(f"❌ An error occurred pulling '{local_relative_path}': {e}", err=True)
            sys.exit(1)

@dotfiles.command(name="status")
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def status(profile, debug):
    """
    Shows the synchronization status of configured dotfiles.
    """
    click.echo(f"ℹ️ Checking dotfiles status for profile '{profile}'...")

    _, bucket_name = get_gcs_profile_config(profile, silent=True, debug=debug)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    dotfiles_gcs_path = gcs_manager.get_dotfiles_gcs_path()

    config, _ = _load_global_config(debug=debug)
    user_home_sync_items = config.get('user_home_sync', [])

    if not user_home_sync_items:
        click.echo("ℹ️ No items configured for 'user_home_sync' in global config. Nothing to check.")
        sys.exit(0)

    status_data = []
    for item in user_home_sync_items:
        local_relative_path = item.get('path')
        if not local_relative_path:
            continue

        local_full_path = os.path.join(os.path.expanduser("~"), local_relative_path)
        gcs_full_path = os.path.join(dotfiles_gcs_path, local_relative_path)

        local_status = _get_local_file_status(local_full_path)
        gcs_status = _get_gcs_file_status(gcs_manager, gcs_full_path)

        sync_status = "N/A"
        if local_status['status'] == "Present" and gcs_status['status'] == "Present":
            if local_status.get('metadata', {}).get('md5_hash') == gcs_status.get('metadata', {}).get('md5_hash'):
                sync_status = "In Sync"
            else:
                sync_status = "Content Differs"
        elif local_status['status'] == "Present":
            sync_status = "Local Only"
        elif gcs_status['status'] == "Present":
            sync_status = "GCS Only"
        else:
            sync_status = "Missing Everywhere"

        status_data.append({
            "File": local_relative_path,
            "Local Status": local_status['status'],
            "GCS Status": gcs_status['status'],
            "Sync Status": sync_status
        })

    click.echo("\n📊 Dotfiles Sync Status:")
    click.echo(_generate_ascii_table(status_data))

