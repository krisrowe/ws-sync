import click
import sys
from devws_cli.setup_commands import setup
from devws_cli.local_commands import local
from devws_cli.config_commands import config
from devws_cli.user_config_commands import user_config
from devws_cli.secrets_commands import secrets # New: Import secrets command group # New: Import user_config command group
# from devws_cli.gcs_profile_commands import gcs_profile # Removed import

@click.group()
def devws():
    """
    A comprehensive CLI for setting up and managing ChromeOS development environments.

    devws streamlines workstation setup and project-specific configuration management.
    """
    pass

devws.add_command(setup)
devws.add_command(local)
devws.add_command(config)
devws.add_command(user_config)
devws.add_command(secrets) # New: Add secrets command group # New: Add user_config command group
# devws.add_command(gcs_profile) # Removed addition

if __name__ == '__main__':
    devws()
