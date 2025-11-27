import click
from devws_cli.precommit import run_precommit

@click.command()
def precommit():
    """
    Scans for sensitive information in the repository.

    This command checks all tracked and untracked files for secrets,
    API keys, and personal information based on your git config,
    .env files, and custom patterns defined in the devws config.
    """
    run_precommit()
