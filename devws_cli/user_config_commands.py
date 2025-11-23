import click
import os
import sys
import yaml # For YAML parsing/dumping

from devws_cli.utils import _load_global_config, GLOBAL_DEVWS_CONFIG_FILE, get_gcs_profile_config
from devws_cli.gcs_manager import GCSManager

@click.group()
def user_config():
    """
    Manages global user configuration files and custom components.
    """
    pass

@user_config.command()
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def backup(profile, debug):
    """
    Backs up the global devws config (~/.config/devws/config.yaml) to GCS.
    """
    click.echo(f"ℹ️ Backing up global devws config for profile '{profile}'...")

    project_id, bucket_name = get_gcs_profile_config(profile)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    user_home_gcs_path = gcs_manager.get_user_home_gcs_path()
    
    if not user_home_gcs_path:
        click.echo(f"❌ Could not determine user home GCS path for profile '{profile}'.", err=True)
        sys.exit(1)

    gcs_config_path = os.path.join(user_home_gcs_path, "devws-config.yaml")

    if not os.path.exists(GLOBAL_DEVWS_CONFIG_FILE):
        click.echo(f"❌ Local devws config file not found at '{GLOBAL_DEVWS_CONFIG_FILE}'. Nothing to backup.", err=True)
        sys.exit(1)
    
    click.echo(f"⬆️ Uploading '{GLOBAL_DEVWS_CONFIG_FILE}' to '{gcs_config_path}'...")
    try:
        if gcs_manager.gcs_cp(GLOBAL_DEVWS_CONFIG_FILE, gcs_config_path, debug=debug):
            click.echo(f"✅ Successfully backed up '{GLOBAL_DEVWS_CONFIG_FILE}' to GCS.")
        else:
            click.echo(f"❌ Failed to backup '{GLOBAL_DEVWS_CONFIG_FILE}' to GCS.", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ An error occurred during backup: {e}", err=True)
        sys.exit(1)


@user_config.command()
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--force', is_flag=True, help='Force overwrite local config if it exists.')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def restore(profile, force, debug):
    """
    Restores the global devws config (~/.config/devws/config.yaml) from GCS.
    """
    click.echo(f"ℹ️ Restoring global devws config for profile '{profile}'...")

    project_id, bucket_name = get_gcs_profile_config(profile)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    user_home_gcs_path = gcs_manager.get_user_home_gcs_path()

    if not user_home_gcs_path:
        click.echo(f"❌ Could not determine user home GCS path for profile '{profile}'.", err=True)
        sys.exit(1)
    
    gcs_config_path = os.path.join(user_home_gcs_path, "devws-config.yaml")

    # Check if local file exists and prompt for overwrite if not forced
    if os.path.exists(GLOBAL_DEVWS_CONFIG_FILE) and not force:
        if not click.confirm(f"⚠️ Local config file '{GLOBAL_DEVWS_CONFIG_FILE}' already exists. Overwrite?"):
            click.echo("Operation cancelled.")
            sys.exit(0)
    elif os.path.exists(GLOBAL_DEVWS_CONFIG_FILE) and force:
        click.echo(f"⚠️ Local config file '{GLOBAL_DEVWS_CONFIG_FILE}' will be overwritten (--force used).")
    
    # Ensure local directory exists
    os.makedirs(os.path.dirname(GLOBAL_DEVWS_CONFIG_FILE), exist_ok=True)

    click.echo(f"⬇️ Downloading '{gcs_config_path}' to '{GLOBAL_DEVWS_CONFIG_FILE}'...")
    try:
        if gcs_manager.gcs_cp(gcs_config_path, GLOBAL_DEVWS_CONFIG_FILE, debug=debug):
            click.echo(f"✅ Successfully restored '{GLOBAL_DEVWS_CONFIG_FILE}' from GCS.")
        else:
            click.echo(f"❌ Failed to restore '{GLOBAL_DEVWS_CONFIG_FILE}' from GCS.", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ An error occurred while updating global config: {e}", err=True)
        sys.exit(1)

@user_config.command(name="push-home")
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def push_home(profile, debug):
    """
    Pushes files and directories specified in 'user_home_sync' from the local home directory to GCS.
    """
    click.echo(f"ℹ️ Pushing user home files for profile '{profile}'...")

    project_id, bucket_name = get_gcs_profile_config(profile)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    user_home_gcs_base_path = gcs_manager.get_user_home_gcs_path()
    
    if not user_home_gcs_base_path:
        click.echo(f"❌ Could not determine user home GCS path for profile '{profile}'.", err=True)
        sys.exit(1)

    global_config_dict, _ = _load_global_config(debug=debug)
    user_home_sync_items = global_config_dict.get('user_home_sync', [])

    if not user_home_sync_items:
        click.echo("ℹ️ No items configured for 'user_home_sync' in global config. Nothing to push.")
        sys.exit(0)

    for item in user_home_sync_items:
        local_relative_path = item.get('path')
        item_type = item.get('type')

        if not local_relative_path or not item_type:
            click.echo(f"⚠️ Skipping malformed user_home_sync item: {item}", err=True)
            continue

        local_full_path = os.path.join(os.path.expanduser("~"), local_relative_path)
        gcs_full_path = os.path.join(user_home_gcs_base_path, local_relative_path)

        if not os.path.exists(local_full_path):
            click.echo(f"⚠️ Local path '{local_full_path}' not found. Skipping '{local_relative_path}'.")
            continue
        
        if item_type == "file" and not os.path.isfile(local_full_path):
            click.echo(f"⚠️ Configured as file but '{local_full_path}' is not a file. Skipping '{local_relative_path}'.", err=True)
            continue
        elif item_type == "directory" and not os.path.isdir(local_full_path):
            click.echo(f"⚠️ Configured as directory but '{local_full_path}' is not a directory. Skipping '{local_relative_path}'.", err=True)
            continue

        click.echo(f"⬆️ Pushing '{local_full_path}' to '{gcs_full_path}'...")
        try:
            if gcs_manager.gcs_cp(local_full_path, gcs_full_path, recursive=(item_type == "directory"), debug=debug):
                click.echo(f"✅ Successfully pushed '{local_relative_path}'.")
            else:
                click.echo(f"❌ Failed to push '{local_relative_path}'.", err=True)
        except Exception as e:
            click.echo(f"❌ An error occurred pushing '{local_relative_path}': {e}", err=True)
            sys.exit(1)


@user_config.command(name="pull-home")
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--force', is_flag=True, help='Force overwrite local files if they exist.')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def pull_home(profile, force, debug):
    """
    Pulls files and directories specified in 'user_home_sync' from GCS to the local home directory.
    """
    click.echo(f"ℹ️ Pulling user home files for profile '{profile}'...")

    project_id, bucket_name = get_gcs_profile_config(profile)
    if not bucket_name:
        click.echo(f"❌ GCS configuration not found for profile '{profile}'. Please run 'devws setup' first.", err=True)
        sys.exit(1)
    
    gcs_manager = GCSManager(bucket_name, profile_name=profile)
    user_home_gcs_base_path = gcs_manager.get_user_home_gcs_path()

    if not user_home_gcs_base_path:
        click.echo(f"❌ Could not determine user home GCS path for profile '{profile}'.", err=True)
        sys.exit(1)
    
    gcs_config_path = os.path.join(user_home_gcs_base_path, "devws-config.yaml")

    global_config_dict, _ = _load_global_config(debug=debug)
    user_home_sync_items = global_config_dict.get('user_home_sync', [])

    if not user_home_sync_items:
        click.echo("ℹ️ No items configured for 'user_home_sync' in global config. Nothing to pull.")
        sys.exit(0)

    for item in user_home_sync_items:
        local_relative_path = item.get('path')
        item_type = item.get('type')

        if not local_relative_path or not item_type:
            click.echo(f"⚠️ Skipping malformed user_home_sync item: {item}", err=True)
            continue

        local_full_path = os.path.join(os.path.expanduser("~"), local_relative_path)
        gcs_full_path = os.path.join(user_home_gcs_base_path, local_relative_path)

        # Check if local path exists and handle force logic
        if os.path.exists(local_full_path) and not force:
            click.echo(f"⚠️ Local path '{local_full_path}' already exists. Use --force to overwrite. Skipping '{local_relative_path}'.")
            continue
        elif os.path.exists(local_full_path) and force:
            click.echo(f"ℹ️ Local path '{local_full_path}' will be overwritten (--force used).")
            # For directories, deleting before pull ensures a clean sync
            if os.path.isdir(local_full_path):
                click.echo(f"ℹ️ Removing existing local directory '{local_full_path}' for clean pull.")
                try:
                    import shutil
                    shutil.rmtree(local_full_path)
                except Exception as e:
                    click.echo(f"❌ Failed to remove local directory '{local_full_path}': {e}", err=True)
                    sys.exit(1)
            elif os.path.isfile(local_full_path):
                click.echo(f"ℹ️ Removing existing local file '{local_full_path}' for clean pull.")
                try:
                    os.remove(local_full_path)
                except Exception as e:
                    click.echo(f"❌ Failed to remove local file '{local_full_path}': {e}", err=True)
                    sys.exit(1)

        # Ensure parent directory exists for local_full_path
        os.makedirs(os.path.dirname(local_full_path), exist_ok=True)

        click.echo(f"⬇️ Pulling '{gcs_full_path}' to '{local_full_path}'...")
        try:
            if gcs_manager.gcs_cp(gcs_full_path, local_full_path, recursive=(item_type == "directory"), debug=debug):
                click.echo(f"✅ Successfully pulled '{local_relative_path}'.")
            else:
                click.echo(f"❌ Failed to pull '{local_relative_path}'.", err=True)
        except Exception as e:
            click.echo(f"❌ An error occurred pulling '{local_relative_path}': {e}", err=True)
            sys.exit(1)

@user_config.command(name="component-add")
@click.option('--id', required=True, help='Unique identifier for the component (used as filename in GCS, without .sh).')
@click.option('--script', 'local_script_path', required=True, type=click.Path(exists=True), help='Path to the local script file (.sh or .py).')
@click.option('--name', help='Human-readable name for the component. Defaults to the ID.')
@click.option('--description', default='No description provided.', help='Brief explanation of what the component does.')
@click.option('--enabled/--disabled', default=True, help='Whether the component is enabled. Defaults to enabled.')
@click.option('--idempotent-check', help='Shell command to check if the component is already completed (exit 0 if true).')
@click.option('--on-failure', type=click.Choice(['abort', 'continue']), default='continue', help='Behavior if the script fails.')
@click.option('--tier', type=click.IntRange(1, 3), default=3, help='Execution priority tier (1:core, 2:common, 3:custom).')
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def component_add(id, local_script_path, name, description, enabled, idempotent_check, on_failure, tier, profile, debug):
    """
    Registers a new custom component script, uploads it to GCS, and adds it to the global devws config.
    """
    click.echo(f"ℹ️ Registering custom component '{id}'...")

    if not name:
        name = id.replace('_', ' ').title()

    # --- Load global config (from GCS or local) ---
    global_config_dict, actual_global_config_file = _load_global_config(debug=debug)
    
    # Ensure custom_components list exists
    if 'custom_components' not in global_config_dict:
        global_config_dict['custom_components'] = []

    # --- Check for ID collision ---
    for existing_comp in global_config_dict['custom_components']:
        if existing_comp.get('id') == id:
            click.echo(f"❌ A custom component with ID '{id}' already exists. Please choose a unique ID.", err=True)
            sys.exit(1)

    # --- Add component to global config ---
    new_component_entry = {
        "id": id,
        "name": name,
        "description": description,
        "enabled": enabled,
        "on_failure": on_failure,
        "tier": tier,
        "script": local_script_path
    }
    if idempotent_check:
        new_component_entry["idempotent_check"] = idempotent_check
    
    global_config_dict['custom_components'].append(new_component_entry)

    # --- Save updated global config locally ---
    click.echo(f"💾 Updating local global config file...")
    try:
        with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
            yaml.safe_dump(global_config_dict, f, default_flow_style=False)
        
        click.echo(f"✅ Successfully registered component '{id}' and updated local config.")
        click.echo(f"ℹ️ Run 'devws config backup' to sync this change to GCS.")
    except Exception as e:
        click.echo(f"❌ An error occurred while updating local global config: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ An error occurred while updating global config: {e}", err=True)
        sys.exit(1)

@user_config.command(name="component-remove")
@click.option('--id', required=True, help='Unique identifier for the component to remove.')
@click.option('--profile', default='default', help='The name of the GCS profile to use. Defaults to "default".')
@click.option('--debug', is_flag=True, help='Show debug output including command execution details.')
def component_remove(id, profile, debug):
    """
    Unregisters a custom component script and updates the global devws config.
    """
    click.echo(f"ℹ️ Removing custom component '{id}'...")

    # --- Load global config ---
    global_config_dict, actual_global_config_file = _load_global_config(debug=debug)
    
    if 'custom_components' not in global_config_dict:
        click.echo(f"❌ No custom components found in the config. Nothing to remove.", err=True)
        sys.exit(1)

    # --- Find and remove component ---
    component_found = False
    original_len = len(global_config_dict['custom_components'])
    global_config_dict['custom_components'] = [
        comp for comp in global_config_dict['custom_components'] if comp.get('id') != id
    ]

    if len(global_config_dict['custom_components']) < original_len:
        component_found = True
    
    if not component_found:
        click.echo(f"❌ Custom component with ID '{id}' not found.", err=True)
        sys.exit(1)
    
    # --- Save updated global config ---
    click.echo(f"💾 Updating local global config file...")
    try:
        with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
            yaml.safe_dump(global_config_dict, f, default_flow_style=False)
        
        click.echo(f"✅ Successfully removed component '{id}' and updated local config.")
        click.echo(f"ℹ️ Run 'devws config backup' to sync this change to GCS.")

    except Exception as e:
        click.echo(f"❌ An error occurred while updating local global config: {e}", err=True)
        sys.exit(1)

