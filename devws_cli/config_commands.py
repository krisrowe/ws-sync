import click
import yaml
import os
from devws_cli.utils import GLOBAL_DEVWS_CONFIG_FILE, _load_global_config

@click.group()
def config():
    """
    Manages global devws configuration settings.
    """
    pass

@config.command(name="view")
def config_view():
    """
    Displays the current global devws configuration.
    """
    config = _load_global_config()
    click.echo(yaml.dump(config, default_flow_style=False))

@config.command(name="set")
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """
    Sets a specific global configuration key to a new value.
    Example: devws config set default_gcs_profile my-profile
    """
    config = _load_global_config()
    
    # Handle nested keys for GCS configuration
    if key.startswith("gcs."):
        parts = key.split('.', 1)
        if len(parts) == 2:
            gcs_config = config.get('gcs', {})
            gcs_config[parts[1]] = value
            config['gcs'] = gcs_config
        else:
            click.echo(f"❌ Invalid GCS configuration key format: {key}", err=True)
            return
    else:
        config[key] = value

    try:
        with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        click.echo(f"✅ Configuration updated: '{key}' set to '{value}'")
    except IOError as e:
        click.echo(f"❌ Error writing to global config file {GLOBAL_DEVWS_CONFIG_FILE}: {e}", err=True)

@config.command(name="set-profile")
@click.argument('profile_name')
def config_set_profile(profile_name):
    """
    Sets the default GCS profile to use for local commands.
    """
    config = _load_global_config()
    config['default_gcs_profile'] = profile_name
    try:
        with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        click.echo(f"✅ Default GCS profile set to '{profile_name}'")
    except IOError as e:
        click.echo(f"❌ Error writing to global config file {GLOBAL_DEVWS_CONFIG_FILE}: {e}", err=True)