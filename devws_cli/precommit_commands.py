import click
from devws_cli.sdk.precommit.scanner import main as run_scanner

@click.command()
@click.argument('repo_path', type=click.Path(exists=True), default='.')
def precommit(repo_path):
    """
    Scans a repository for sensitive information.

    Performs comprehensive checks including:
    - Git history (commits, file content, filenames, commit messages)
    - Detached/orphan commits and stash entries
    - Branch and tag names
    - Local filesystem (bypassing .gitignore)
    - Dollar amounts (large, non-round, with cents)
    
    REPO_PATH: Path to repository to scan (default: current directory)
    """
    import sys
    # scanner.main() uses argparse, so we need to set sys.argv
    sys.argv = ['devws precommit', repo_path]
    run_scanner()


