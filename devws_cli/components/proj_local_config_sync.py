import click
import sys
from devws_cli.utils import _log_step, _load_global_config
from devws_cli.managers.locals_manager import LocalsManager

def setup(config):
    """
    Manages the GCS Synchronization Configuration.
    """
    if not config.get("enabled", True):
        _log_step("GCS Synchronization Configuration", "DISABLED")
        return

    click.echo("\nStep 8: GCS Synchronization Configuration")
    
    # Reload global config as it might have been updated by _configure_gcs_sync
    global_config, actual_global_config_file = _load_global_config()

    locals_manager = LocalsManager() # Instantiate LocalsManager
    
    # Get project_id, bucket_name, and profile from component config (which might be overridden by CLI args)
    arg_project_id = config.get("project_id")
    arg_bucket_name = config.get("bucket_name")
    profile_name = config.get("profile", "default") # Default to 'default' if not provided

    updated_global_config, success, messages, error_message = locals_manager.configure_gcs_sync(arg_project_id, arg_bucket_name, profile_name, global_config, actual_global_config_file)
    
    for msg in messages:
        click.echo(msg)

    if error_message:
        click.echo(f"❌ {error_message}", err=True)
        _log_step("GCS Synchronization Configuration", "FAIL", error_message)
        sys.exit(1)
    elif success:
        _log_step("GCS Synchronization Configuration", "COMPLETED", f"GCS configured for profile 'default'.")
    else:
        _log_step("GCS Synchronization Configuration", "FAIL", f"Failed to configure GCS for profile 'default'.")
        sys.exit(1) # Should not happen if error_message is set for failures.
    click.echo("-" * 60)
