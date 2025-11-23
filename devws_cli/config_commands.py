import click
import yaml
import os
from devws_cli.utils import GLOBAL_DEVWS_CONFIG_FILE, _load_global_config

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