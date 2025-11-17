import click
import sys
from devws_cli.setup_commands import setup
from devws_cli.local_commands import local
from devws_cli.config_commands import config
# from devws_cli.gcs_profile_commands import gcs_profile # Removed import

@click.group()
def devws():
    """
    devws CLI for managing ChromeOS development environment.
    """
    pass

devws.add_command(setup)
devws.add_command(local)
devws.add_command(config)
# devws.add_command(gcs_profile) # Removed addition

if __name__ == '__main__':
    devws()
