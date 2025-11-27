
import click
import os
from devws_cli.backup import create_home_backup
from devws_cli.utils import _load_global_config, get_gcs_profile_config
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
        gcs_backup_path = f"{gcs_manager.get_user_home_gcs_path()}/backups/"
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
