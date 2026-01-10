import os
import subprocess
import click # For click.echo
from devws_cli.utils import _run_command, get_git_repo_info # Import the moved utility

class GCSManager:
    def __init__(self, bucket_name, profile_name='default'):
        self.bucket_name = bucket_name
        self.profile_name = profile_name
        self.bucket_url = f"gs://{self.bucket_name}"

    def _get_repo_identifier(self):
        """
        Retrieves the Git repository owner and name to form a unique identifier.
        """
        owner, repo_name = get_git_repo_info()
        if not owner or not repo_name:
            click.echo("Error: Not in a Git repository or could not determine repo info.", err=True)
            return None
        return f"{owner}/{repo_name}"

    def get_repo_gcs_path(self, repo_identifier=None):
        """
        Returns the GCS path for a repository's configurations.
        If repo_identifier is None, tries to get it from current git repo.
        """
        if repo_identifier is None:
            repo_identifier = self._get_repo_identifier()
        if repo_identifier:
            return f"{self.bucket_url}/repos/{repo_identifier}"
        return None

    def get_tool_config_gcs_path(self):
        """
        Returns the GCS path for devws tool configuration.
        """
        return f"{self.bucket_url}/devws/"

    def get_home_backups_gcs_path(self):
        """
        Returns the GCS path for home directory backup archives.
        """
        return f"{self.bucket_url}/home/backups/"

    def get_dotfiles_gcs_path(self):
        """
        Returns the GCS path for synchronized dotfiles.
        """
        return f"{self.bucket_url}/home/dotfiles/"

    def get_user_components_gcs_path(self):
        """
        Returns the GCS path for custom component scripts.
        """
        return f"{self.bucket_url}/user-components"

    def gcs_cp(self, source, destination, recursive=False, debug=False):
        """
        Wrapper for gsutil cp command, abstracting source/destination.
        Source or destination can be a local path or a full gs:// path.
        """
        command = ['gsutil']
        if not debug:
            command.append('-q') # Quiet mode
        command.append('cp') # Add 'cp' command
        if recursive:
            command.append('-r')
        command.extend([source, destination])
        return _run_command(command, check=True, debug=debug)

    def gcs_rm(self, path, recursive=False, debug=False):
        """
        Wrapper for gsutil rm command.
        Path should be a full gs:// path.
        """
        command = ['gsutil']
        if not debug:
            command.append('-q') # Quiet mode unless debug is enabled
        if recursive:
            command.append('-r')
        command.extend(['rm', path])
        return _run_command(command, check=True, debug=debug)

    def gcs_ls(self, path, recursive=False, debug=False):
        """
        Wrapper for gsutil ls command.
        Path should be a full gs:// path or prefix.
        Returns stdout (list of paths) if successful, or empty list on error.
        """
        command = ['gsutil', 'ls']
        if not debug:
            command.append('-d') # Only list directories and files directly specified
        if recursive:
            command.append('-r')
        command.append(path)
        try:
            result = _run_command(command, capture_output=True, check=True, debug=debug)
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError:
            return [] # Return empty list if path not found or error

    def gcs_stat(self, path, debug=False):
        """
        Wrapper for gsutil stat command.
        Path should be a full gs:// path to an object.
        Returns stat output as a dictionary or None if not found/error.
        """
        command = ['gsutil', 'stat', path]
        try:
            result = _run_command(command, capture_output=True, check=True, debug=debug)
            # gsutil stat gives key: value pairs per line
            # We'll parse it into a dict for convenience
            stats = {}
            for line in result.stdout.splitlines():
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    stats[key.strip()] = value.strip()
            return stats
        except subprocess.CalledProcessError as e:
            click.echo(f"DEBUG: gsutil stat failed for {path}: {e}", err=True)
            return None # Return None if not found or error

    def gcs_mv(self, source, destination, recursive=False, debug=False):
        """
        Wrapper for gsutil mv command, abstracting source/destination.
        Source and destination can be local paths or full gs:// paths.
        """
        command = ['gsutil']
        if not debug:
            command.append('-q')  # Quiet mode unless debug is enabled
        if recursive:
            command.append('-r')
        command.extend(['mv', source, destination])
        return _run_command(command, check=True, debug=debug)
