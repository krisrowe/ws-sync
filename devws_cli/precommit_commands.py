import click
from devws_cli.precommit import run_precommit

@click.command()
@click.option('--verbose', '-v', is_flag=True, help='Show intentionally ignored false positives (e.g., author name in LICENSE).')
def precommit(verbose):
    """
    Scans for sensitive information in the repository.

    This command checks all tracked and untracked files for secrets,
    API keys, and personal information based on your git config,
    .env files, and custom patterns defined in the devws config.

    Known false positives (like author names in LICENSE files) are
    automatically suppressed. Use --verbose to see them.
    """
    run_precommit(verbose=verbose)
