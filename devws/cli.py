import click
import sys
from devws_cli.setup_commands import setup
from devws_cli.local_commands import local
from devws_cli.config_commands import config
from devws_cli.secrets_commands import secrets
from devws_cli.home_commands import home
from devws_cli.precommit_commands import precommit
from devws_cli.repo_commands import repo
from devws_cli.chromeos.commands import chrome
from devws_cli.gitignore_commands import gitignore

@click.group()
def devws():
    """
    A comprehensive CLI for setting up and managing Linux development environments.

    devws streamlines workstation setup and project-specific configuration management.
    """
    pass

devws.add_command(setup)
devws.add_command(local)
devws.add_command(config)
devws.add_command(secrets)
devws.add_command(home)
devws.add_command(precommit)
devws.add_command(repo)
devws.add_command(chrome)
devws.add_command(gitignore)

if __name__ == '__main__':
    devws()
