"""Repository-level commands for devws CLI."""

import click
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


def parse_user_files_from_gitignore(gitignore_path: Path) -> list[str]:
    """
    Parse .gitignore and return patterns listed under '# user-files' section.

    The section ends at EOF or the next blank line.
    """
    if not gitignore_path.exists():
        return []

    patterns = []
    in_user_files_section = False

    with open(gitignore_path) as f:
        for line in f:
            line = line.rstrip('\n')

            if line.strip() == '# user-files':
                in_user_files_section = True
                continue

            if in_user_files_section:
                # End section on blank line or EOF
                if line.strip() == '':
                    break
                # Skip comments within section
                if line.strip().startswith('#'):
                    continue
                patterns.append(line.strip())

    return patterns


def find_matching_files(repo_root: Path, patterns: list[str]) -> list[Path]:
    """
    Find files in repo_root matching the given glob patterns.
    """
    import fnmatch

    matching_files = []

    for pattern in patterns:
        # Handle simple glob patterns
        for path in repo_root.iterdir():
            if path.is_file() and fnmatch.fnmatch(path.name, pattern):
                matching_files.append(path)

    return list(set(matching_files))  # Remove duplicates


def get_git_remote_config(repo_root: Path) -> str:
    """
    Get git remote configuration for documentation purposes.
    """
    git_config_path = repo_root / '.git' / 'config'
    if not git_config_path.exists():
        return ""

    with open(git_config_path) as f:
        content = f.read()

    # Extract just the remote sections
    lines = content.split('\n')
    remote_lines = []
    in_remote_section = False

    for line in lines:
        if line.strip().startswith('[remote'):
            in_remote_section = True
        elif line.strip().startswith('[') and in_remote_section:
            in_remote_section = False

        if in_remote_section:
            remote_lines.append(line)

    return '\n'.join(remote_lines)


def get_repo_name(repo_root: Path) -> str:
    """
    Get repository name from git remote origin.

    Extracts final path segment (e.g., 'repo.git' or 'repo') from the origin URL.
    Falls back to directory name if no origin remote.
    """
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract final path segment from URL
            # Handles: git@github.com:user/repo.git or https://github.com/user/repo.git
            match = re.search(r'/([^/]+)$', url)
            if match:
                return match.group(1)  # Returns "repo.git" or "repo"
    except Exception:
        pass

    return repo_root.name


def read_backup_config(repo_root: Path) -> dict:
    """Read user-backup.yaml configuration."""
    import yaml

    config_path = repo_root / 'user-backup.yaml'
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def get_gwsa_token_path() -> Path:
    """Get the path to the gwsa user token."""
    return Path.home() / ".config" / "gworkspace-access" / "user_token.json"


def upload_to_google_drive(zip_path: Path, folder_id: str) -> str:
    """
    Upload zip file to Google Drive folder and return the file URL.

    Uses the gwsa token from ~/.config/gworkspace-access/user_token.json
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token_path = get_gwsa_token_path()
    if not token_path.exists():
        raise FileNotFoundError(
            f"gwsa token not found at {token_path}. "
            "Run 'gwsa setup --new-user' to authenticate with Drive access."
        )

    creds = Credentials.from_authorized_user_file(str(token_path))

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': zip_path.name,
        'parents': [folder_id]
    }

    media = MediaFileUpload(str(zip_path), mimetype='application/zip')

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    return file.get('webViewLink', f"https://drive.google.com/file/d/{file.get('id')}/view")


@click.group()
def repo():
    """Repository-level commands."""
    pass


@repo.command('user-archive')
@click.option('--dry-run', is_flag=True, help='Show what would be archived without uploading')
@click.option('--target-folder', help='Google Drive folder ID (overrides user-backup.yaml)')
def user_archive(dry_run: bool, target_folder: str):
    """
    Archive user-specific files from this repo to Google Drive.

    Reads patterns from the '# user-files' section in .gitignore,
    finds matching files, and uploads a zip archive to the Google Drive
    folder specified via --target-folder or user-backup.yaml.

    The archive includes:
    - All files matching patterns under '# user-files' in .gitignore
    - Git remote configuration (for documentation)

    Folder ID can be specified via:
    - --target-folder <folder_id>
    - user-backup.yaml with: folder: <folder_id>
    """
    # Find repo root
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            check=True
        )
        repo_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        click.echo("Error: Not in a git repository", err=True)
        raise SystemExit(1)

    gitignore_path = repo_root / '.gitignore'

    # Parse user-files patterns
    patterns = parse_user_files_from_gitignore(gitignore_path)
    if not patterns:
        click.echo("Error: No patterns found under '# user-files' section in .gitignore", err=True)
        raise SystemExit(1)

    click.echo(f"User-file patterns from .gitignore: {patterns}")

    # Find matching files
    user_files = find_matching_files(repo_root, patterns)
    if not user_files:
        click.echo("Error: No user files found matching the patterns", err=True)
        raise SystemExit(1)

    click.echo(f"\nUser files to archive ({len(user_files)}):")
    for f in sorted(user_files):
        click.echo(f"  - {f.name}")

    # Get folder ID from --target-folder or user-backup.yaml
    folder_id = target_folder
    if not folder_id:
        backup_config = read_backup_config(repo_root)
        folder_id = backup_config.get('folder')

    if not folder_id and not dry_run:
        click.echo("\nError: No folder ID specified", err=True)
        click.echo("Provide via --target-folder or create user-backup.yaml with:", err=True)
        click.echo("  folder: <Google Drive folder ID>", err=True)
        raise SystemExit(1)

    # Get repo name and create archive name
    # repo_name is like "gdoc-form-filler.git" or "gdoc-form-filler"
    repo_name = get_repo_name(repo_root)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M')
    archive_name = f"{repo_name}_{timestamp}.zip"

    # Determine if target is local path or Google Drive folder ID
    # Local paths contain . or / (e.g., ".", "./backups", "../foo", "/tmp")
    is_local_path = folder_id and ('.' in folder_id or '/' in folder_id)

    if dry_run:
        click.echo(f"\n[Dry run] Would create archive: {archive_name}")
        if is_local_path:
            click.echo(f"[Dry run] Would save to local path: {folder_id}")
        else:
            click.echo(f"[Dry run] Would upload to Google Drive folder: {folder_id or '(not configured)'}")
        return

    # Create zip archive
    if is_local_path:
        # Save locally
        local_dir = Path(folder_id).expanduser().resolve()
        local_dir.mkdir(parents=True, exist_ok=True)
        zip_path = local_dir / archive_name

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in user_files:
                zf.write(f, f.name)
            remote_config = get_git_remote_config(repo_root)
            if remote_config:
                zf.writestr('git-remotes.txt', remote_config)

        click.echo(f"\nArchive saved locally:")
        click.echo(f"  {zip_path}")
    else:
        # Upload to Google Drive
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / archive_name

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in user_files:
                    zf.write(f, f.name)
                remote_config = get_git_remote_config(repo_root)
                if remote_config:
                    zf.writestr('git-remotes.txt', remote_config)

            click.echo(f"\nCreated archive: {archive_name}")
            click.echo(f"Uploading to Google Drive folder {folder_id}...")

            try:
                file_url = upload_to_google_drive(zip_path, folder_id)
                click.echo(f"\nSuccess! Archive uploaded:")
                click.echo(f"  {file_url}")
            except Exception as e:
                click.echo(f"\nError uploading to Google Drive: {e}", err=True)
                raise SystemExit(1)
