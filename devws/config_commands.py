import click
import yaml
import os
import sys
from devws_cli.utils import GLOBAL_DEVWS_CONFIG_FILE, _load_global_config, get_gcs_profile_config
from devws_cli.gcs_manager import GCSManager

@click.group()
def config():
    """
    Manages the global devws configuration settings.

    This command group allows you to view and modify the central
    configuration file used by devws for various operations.
    """
    pass

@config.command(name="view")
def config_view():
    """
    Displays the current global devws configuration.
    """
    config, _ = _load_global_config() # Unpack the tuple
    click.echo(yaml.dump(config, default_flow_style=False))

@config.command(name="set")
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """
    Sets a specific global configuration key to a new value.
    Example: devws config set default_gcs_profile my-profile
    """
    config, actual_global_config_file = _load_global_config() # Unpack the tuple
    
    # Handle nested keys for GCS configuration
    if key.startswith("gcs_profiles.default."): # Adjusting key prefix for clarity
        parts = key.split('.', 2) # Split by '.' at most twice
        if len(parts) == 3 and parts[0] == "gcs_profiles" and parts[1] == "default":
            # Ensure gcs_profiles and default profile exist
            if 'gcs_profiles' not in config:
                config['gcs_profiles'] = {}
            if 'default' not in config['gcs_profiles']:
                config['gcs_profiles']['default'] = {}
            
            config['gcs_profiles']['default'][parts[2]] = value
        else:
            click.echo(f"❌ Invalid GCS configuration key format: {key}. Expected 'gcs_profiles.default.<key>'.", err=True)
            return
    elif key == "default_gcs_profile": # Handle direct default_gcs_profile key
        config[key] = value
    else:
        # For other top-level keys
        config[key] = value

    try:
        with open(actual_global_config_file, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        click.echo(f"✅ Configuration updated: '{key}' set to '{value}'")
    except IOError as e:
        click.echo(f"❌ Error writing to global config file {actual_global_config_file}: {e}", err=True)

@config.command(name="set-profile")
@click.argument('profile_name')
def config_set_profile(profile_name):
    """
    Sets the default GCS profile to use for local commands.
    """
    config, actual_global_config_file = _load_global_config() # Unpack the tuple
    config['default_gcs_profile'] = profile_name
    try:
        with open(actual_global_config_file, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        click.echo(f"✅ Default GCS profile set to '{profile_name}'")
    except IOError as e:
        click.echo(f"❌ Error writing to global config file {actual_global_config_file}: {e}", err=True)

@config.command()
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def backup(profile, debug):
    """
    Backs up the global devws config (~/.config/devws/config.yaml) to GCS.
    """
    click.echo(f"ℹ️ Backing up global devws config for profile '{profile}'...")

    project_id, bucket_name = get_gcs_profile_config(profile)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    tool_config_gcs_path = gcs_manager.get_tool_config_gcs_path()
    
    if not tool_config_gcs_path:
        click.echo(f"❌ Could not determine tool config GCS path for profile '{profile}'.", err=True)
        sys.exit(1)

    gcs_config_path = os.path.join(tool_config_gcs_path, "config.yaml")

    if not os.path.exists(GLOBAL_DEVWS_CONFIG_FILE):
        click.echo(f"❌ Local devws config file not found at '{GLOBAL_DEVWS_CONFIG_FILE}'. Nothing to backup.", err=True)
        sys.exit(1)
    
    click.echo(f"⬆️ Uploading '{GLOBAL_DEVWS_CONFIG_FILE}' to '{gcs_config_path}'...")
    try:
        if gcs_manager.gcs_cp(GLOBAL_DEVWS_CONFIG_FILE, gcs_config_path, debug=debug):
            click.echo(f"✅ Successfully backed up '{GLOBAL_DEVWS_CONFIG_FILE}' to GCS.")
        else:
            click.echo(f"❌ Failed to backup '{GLOBAL_DEVWS_CONFIG_FILE}' to GCS.", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ An error occurred during backup: {e}", err=True)
        sys.exit(1)


@config.command()
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--force', is_flag=True, help='Force overwrite local config if it exists.')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def restore(profile, force, debug):
    """
    Restores the global devws config (~/.config/devws/config.yaml) from GCS.
    """
    click.echo(f"ℹ️ Restoring global devws config for profile '{profile}'...")

    project_id, bucket_name = get_gcs_profile_config(profile)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    tool_config_gcs_path = gcs_manager.get_tool_config_gcs_path()

    if not tool_config_gcs_path:
        click.echo(f"❌ Could not determine tool config GCS path for profile '{profile}'.", err=True)
        sys.exit(1)
    
    gcs_config_path = os.path.join(tool_config_gcs_path, "config.yaml")

    # Check if local file exists and prompt for overwrite if not forced
    if os.path.exists(GLOBAL_DEVWS_CONFIG_FILE) and not force:
        if not click.confirm(f"⚠️ Local config file '{GLOBAL_DEVWS_CONFIG_FILE}' already exists. Overwrite?"):
            click.echo("Operation cancelled.")
            sys.exit(0)
    elif os.path.exists(GLOBAL_DEVWS_CONFIG_FILE) and force:
        click.echo(f"⚠️ Local config file '{GLOBAL_DEVWS_CONFIG_FILE}' will be overwritten (--force used).")
    
    # Ensure local directory exists
    os.makedirs(os.path.dirname(GLOBAL_DEVWS_CONFIG_FILE), exist_ok=True)

    click.echo(f"⬇️ Downloading '{gcs_config_path}' to '{GLOBAL_DEVWS_CONFIG_FILE}'...")
    try:
        if gcs_manager.gcs_cp(gcs_config_path, GLOBAL_DEVWS_CONFIG_FILE, debug=debug):
            click.echo(f"✅ Successfully restored '{GLOBAL_DEVWS_CONFIG_FILE}' from GCS.")
        else:
            click.echo(f"❌ Failed to restore '{GLOBAL_DEVWS_CONFIG_FILE}' from GCS.", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ An error occurred while updating global config: {e}", err=True)
        sys.exit(1)