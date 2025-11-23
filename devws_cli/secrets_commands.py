import click
import os
import sys
try:
    from google.cloud import secretmanager # Requires 'google-cloud-secret-manager'
    HAS_SECRET_MANAGER = True
except ImportError:
    HAS_SECRET_MANAGER = False
from devws_cli.utils import _load_global_config, get_gcs_profile_config

@click.group()
def secrets():
    """
    Manages sensitive data using Google Cloud Secret Manager.
    """
    pass

def _get_secret_manager_client_and_project_id(project_id_arg=None):
    """
    Helper to get a Secret Manager client and the resolved project ID.
    """
    # Prefer project_id from argument, then global config, then gcloud default
    resolved_project_id = project_id_arg
    if not resolved_project_id:
        global_config, _ = _load_global_config()
        resolved_project_id = global_config.get('default_gcp_project_id')
    if not resolved_project_id:
        try:
            result = _run_command(['gcloud', 'config', 'get-value', 'project'], capture_output=True, check=True)
            resolved_project_id = result.stdout.strip()
        except Exception:
            pass # Will be handled by the next check

    if not resolved_project_id:
        click.echo(f"❌ Google Cloud Project ID not found. Please specify with --project-id, set 'default_gcp_project_id' in your global config, or configure gcloud default project.", err=True)
        sys.exit(1)

    try:
        client = secretmanager.SecretManagerServiceClient()
        return client, resolved_project_id
    except Exception as e:
        click.echo(f"❌ Failed to initialize Google Cloud Secret Manager client: {e}", err=True)
        click.echo("Ensure 'google-cloud-secret-manager' library is installed and gcloud is authenticated.", err=True)
        sys.exit(1)


@secrets.command(name="put")
@click.argument('name')
@click.option('--value', help='The secret value to store.')
@click.option('--file', 'file_path', type=click.Path(exists=True), help='Path to a file whose content will be stored as the secret.')
@click.option('--project-id', help='Google Cloud Project ID (overrides global config and gcloud default).')
def put_secret(name, value, file_path, project_id):
    """
    Stores a secret in Google Cloud Secret Manager.
    Content can be provided directly or from a file.
    """
    if not value and not file_path:
        click.echo("❌ Either --value or --file must be provided.", err=True)
        sys.exit(1)
    if value and file_path:
        click.echo("❌ Cannot use both --value and --file. Choose one.", err=True)
        sys.exit(1)

    secret_data = None
    if value:
        secret_data = value.encode('utf-8')
    elif file_path:
        try:
            with open(file_path, 'rb') as f:
                secret_data = f.read()
        except IOError as e:
            click.echo(f"❌ Failed to read file '{file_path}': {e}", err=True)
            sys.exit(1)

    client, resolved_project_id = _get_secret_manager_client_and_project_id(project_id)
    parent = f"projects/{resolved_project_id}"

    try:
        # Check if the secret already exists
        try:
            client.get_secret(request={"name": f"{parent}/secrets/{name}"})
            # Secret exists, add a new version
            response = client.add_secret_version(
                request={"parent": f"{parent}/secrets/{name}", "payload": {"data": secret_data}}
            )
            click.echo(f"✅ New version of secret '{name}' added: {response.name}")
        except Exception as e:
            # Secret does not exist, create it
            response = client.create_secret(
                request={"parent": parent, "secret_id": name, "secret": {"replication": {"automatic": {}}}}
            )
            client.add_secret_version(
                request={"parent": response.name, "payload": {"data": secret_data}}
            )
            click.echo(f"✅ Secret '{name}' created and first version added: {response.name}")

    except Exception as e:
        click.echo(f"❌ Failed to store secret '{name}': {e}", err=True)
        sys.exit(1)


@secrets.command(name="get")
@click.argument('name')
@click.option('--output-file', type=click.Path(), help='Path to save the secret to. If not provided, prints to stdout.')
@click.option('--project-id', help='Google Cloud Project ID (overrides global config and gcloud default).')
def get_secret(name, output_file, project_id):
    """
    Retrieves a secret from Google Cloud Secret Manager.
    """
    client, resolved_project_id = _get_secret_manager_client_and_project_id(project_id)
    secret_name = f"projects/{resolved_project_id}/secrets/{name}/versions/latest"

    try:
        response = client.access_secret_version(request={"name": secret_name})
        secret_data = response.payload.data

        if output_file:
            try:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, 'wb') as f:
                    f.write(secret_data)
                click.echo(f"✅ Secret '{name}' saved to '{output_file}'.")
                # Adjust permissions for sensitive files like SSH keys
                if os.path.basename(output_file).startswith("id_rsa"):
                    os.chmod(output_file, 0o600)
                    click.echo(f"ℹ️ Adjusted permissions for '{output_file}' to 0600.")
            except IOError as e:
                click.echo(f"❌ Failed to write secret to file '{output_file}': {e}", err=True)
                sys.exit(1)
        else:
            sys.stdout.buffer.write(secret_data)
            click.echo() # Add a newline for clean output
    except Exception as e:
        click.echo(f"❌ Failed to retrieve secret '{name}': {e}", err=True)
        sys.exit(1)
