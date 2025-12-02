"""Repository-level commands for devws CLI.

User Archive Design Notes
-------------------------
The user-archive command includes a git bundle by default alongside user files.
This ensures the archive is self-contained and useful even if:
- The remote repository is later deleted
- The GitHub account is lost or inaccessible
- The repo was primarily created to support work on the user files

User files without the associated tooling/code may become meaningless. Including
the bundle preserves the full context needed to restore and continue work.

Git Bundle Safety Analysis
--------------------------
A git bundle contains the same data available when cloning a public repository:
- All commits, branches, and tags
- Complete version history of tracked files
- No untracked or gitignored files (user files, credentials, etc.)

What a bundle does NOT include:
- .git/config (remotes, local settings, hooks)
- Untracked files
- Files in .gitignore (credentials, tokens, user data)
- Local refs like stashes

For a public repo, the bundle contains nothing beyond what anyone can already
access via `git clone`. For private repos, the bundle should be stored with
the same care as the repo itself. The archive combines:
1. Git bundle - equivalent to a clone of the repo
2. User files - the sensitive/local data not in version control
3. Git remotes - documents where the repo was hosted (for reference)
"""

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


def create_git_bundle(repo_root: Path, output_path: Path) -> bool:
    """
    Create a git bundle containing all branches and tags.

    Returns True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ['git', 'bundle', 'create', str(output_path), '--all'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def get_git_head_info(repo_root: Path) -> tuple[str, str]:
    """
    Get the current branch name and commit hash.

    Returns (branch_name, commit_hash). Branch may be empty if in detached HEAD state.
    """
    branch = ""
    commit = ""

    try:
        # Get current branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch == "HEAD":
                branch = "(detached HEAD)"
    except Exception:
        pass

    try:
        # Get current commit hash
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
    except Exception:
        pass

    return branch, commit


def generate_archive_readme(repo_name: str, user_files: list[Path], patterns: list[str],
                            has_bundle: bool, remote_config: str,
                            branch: str, commit: str) -> str:
    """
    Generate REPO-ARCHIVE.md content describing the archive and restoration steps.
    """
    user_file_list = '\n'.join(f'- `{f.name}`' for f in sorted(user_files))
    pattern_list = '\n'.join(f'- `{p}`' for p in patterns)

    # State at archive time
    state_section = ""
    if branch or commit:
        state_section = f"""
## State at Archive Time

- **Branch:** `{branch}`
- **Commit:** `{commit}`
"""

    remote_section = ""
    if remote_config:
        # Parse the remote config to extract URLs for the commands
        import re as re_module
        remote_commands = []
        current_remote = None
        for line in remote_config.split('\n'):
            remote_match = re_module.match(r'\[remote "(.+)"\]', line.strip())
            if remote_match:
                current_remote = remote_match.group(1)
            url_match = re_module.match(r'url\s*=\s*(.+)', line.strip())
            if url_match and current_remote:
                remote_commands.append(f"git remote add {current_remote} {url_match.group(1)}")

        commands_text = '\n'.join(remote_commands) if remote_commands else "git remote add origin <url>"

        remote_section = f"""
## Git Remotes

The original remote configuration from `git-remotes.txt`:

```
{remote_config}
```

After restoring from the bundle, re-attach to remotes (if still available):

```bash
{commands_text}
```

Then verify and sync:

```bash
git fetch --all
git branch -u origin/main main  # Set upstream tracking
```
"""

    # Parse remote config to get clone URL for instructions
    clone_url = "<url-from-git-remotes.txt>"
    if remote_config:
        import re as re_module
        for line in remote_config.split('\n'):
            url_match = re_module.match(r'\s*url\s*=\s*(.+)', line)
            if url_match:
                clone_url = url_match.group(1)
                break

    checkout_cmd = f"git checkout {commit[:12]}" if commit else "git checkout <commit-hash>"

    bundle_section = ""
    if has_bundle:
        bundle_section = """
## Restoring the Repository from repo.bundle

The `repo.bundle` file contains the complete git repository (all branches, tags,
and history). To restore:

```bash
# Clone from the bundle (creates a new directory)
git clone repo.bundle <repo-name>

# Or restore into an existing empty directory
cd <repo-name>
git init
git pull ../repo.bundle --all
```

After cloning from a bundle, you may want to:
1. Add the original remote (see Git Remotes section below)
2. Fetch from remote to verify you're up to date
"""

    # Always include restore-from-remote section, but note its importance when no bundle
    no_bundle_note = ""
    if not has_bundle:
        no_bundle_note = """**Note:** This archive does not include a git bundle, so restoring from the
remote is the only way to recover the repository code.

"""

    restore_from_remote = f"""
## Restoring the Repository from Remote

{no_bundle_note}If the remote is still available, clone and restore to the archived state:

```bash
git clone {clone_url}
cd <repo-name>
```

To restore to the exact commit when this archive was created:

```bash
{checkout_cmd}
```

Or to check out the branch:

```bash
git checkout {branch}
```
"""

    bundle_section = bundle_section + restore_from_remote

    return f"""# Repository Archive: {repo_name}

This archive contains a backup of user-specific files and repository data.
{state_section}
## Archive Contents

- `REPO-ARCHIVE.md` - This file
- `repo.bundle` - Complete git repository (if included)
- `git-remotes.txt` - Original remote URLs for reference
- User files (see below)

## User Files

These files were backed up from patterns in the `# user-files` section of `.gitignore`:

Patterns:
{pattern_list}

Files included:
{user_file_list}
{bundle_section}{remote_section}
## Restoring User Files

After restoring the repository:

1. The `.gitignore` file in the restored repo contains a `# user-files` section
   listing the patterns for these files
2. Copy the user files from this archive to the repository root
3. They will be automatically ignored by git (already in `.gitignore`)

```bash
# Example restoration workflow
git clone repo.bundle my-project
cd my-project
cp ../user-answers.csv .
cp ../config.yaml .
# etc.
```

## Notes

- User files are gitignored and contain user-specific data (config, answers, etc.)
- The git bundle contains only versioned files - no credentials or user data
- For private repositories, treat this archive with the same care as the repo itself
"""


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
@click.option('--target-folder', help='Google Drive folder ID or local path (overrides user-backup.yaml)')
@click.option('--no-bundle', is_flag=True, help='Exclude git bundle from archive')
def user_archive(dry_run: bool, target_folder: str, no_bundle: bool):
    """
    Archive user-specific files and git bundle from this repo.

    Creates a zip archive containing:
    - Git bundle (full repo clone, excludes untracked/gitignored files)
    - User files matching patterns under '# user-files' in .gitignore
    - Git remote configuration (for reference)

    The git bundle is included by default to ensure the archive remains
    useful even if the remote repository becomes unavailable.

    Target can be specified via:
    - --target-folder <folder_id> (Google Drive)
    - --target-folder <path> (local, if contains . or /)
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
        if not no_bundle:
            click.echo("[Dry run] Would include: git bundle (repo.bundle)")
        if is_local_path:
            click.echo(f"[Dry run] Would save to local path: {folder_id}")
        else:
            click.echo(f"[Dry run] Would upload to Google Drive folder: {folder_id or '(not configured)'}")
        return

    # Get info needed for README generation
    remote_config = get_git_remote_config(repo_root)
    branch, commit = get_git_head_info(repo_root)
    has_bundle = not no_bundle

    # Create zip archive
    if is_local_path:
        # Save locally
        local_dir = Path(folder_id).expanduser().resolve()
        local_dir.mkdir(parents=True, exist_ok=True)
        zip_path = local_dir / archive_name

        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add git bundle if not excluded
                bundle_created = False
                if has_bundle:
                    bundle_path = Path(tmpdir) / 'repo.bundle'
                    if create_git_bundle(repo_root, bundle_path):
                        zf.write(bundle_path, 'repo.bundle')
                        click.echo("Added: repo.bundle")
                        bundle_created = True
                    else:
                        click.echo("Warning: Failed to create git bundle", err=True)

                # Add user files
                for f in user_files:
                    zf.write(f, f.name)

                # Add remote config
                if remote_config:
                    zf.writestr('git-remotes.txt', remote_config)

                # Add REPO-ARCHIVE.md
                readme_content = generate_archive_readme(
                    repo_name, user_files, patterns, bundle_created, remote_config,
                    branch, commit
                )
                zf.writestr('REPO-ARCHIVE.md', readme_content)

        click.echo(f"\nArchive saved locally:")
        click.echo(f"  {zip_path}")
    else:
        # Upload to Google Drive
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / archive_name

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add git bundle if not excluded
                bundle_created = False
                if has_bundle:
                    bundle_path = Path(tmpdir) / 'repo.bundle'
                    if create_git_bundle(repo_root, bundle_path):
                        zf.write(bundle_path, 'repo.bundle')
                        click.echo("Added: repo.bundle")
                        bundle_created = True
                    else:
                        click.echo("Warning: Failed to create git bundle", err=True)

                # Add user files
                for f in user_files:
                    zf.write(f, f.name)

                # Add remote config
                if remote_config:
                    zf.writestr('git-remotes.txt', remote_config)

                # Add REPO-ARCHIVE.md
                readme_content = generate_archive_readme(
                    repo_name, user_files, patterns, bundle_created, remote_config,
                    branch, commit
                )
                zf.writestr('REPO-ARCHIVE.md', readme_content)

            click.echo(f"\nCreated archive: {archive_name}")
            click.echo(f"Uploading to Google Drive folder {folder_id}...")

            try:
                file_url = upload_to_google_drive(zip_path, folder_id)
                click.echo(f"\nSuccess! Archive uploaded:")
                click.echo(f"  {file_url}")
            except Exception as e:
                click.echo(f"\nError uploading to Google Drive: {e}", err=True)
                raise SystemExit(1)
