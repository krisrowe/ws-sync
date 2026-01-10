import click
import sys
from devws_cli.utils import _log_step, _load_global_config
from devws_cli.gcs_profile_manager import GCSProfileManager  # Updated import

def setup(config, dry_run=False):
    """
    Manages project local configuration synchronization.
    """
    category = config.get("category", "custom")
    
    if not config.get("enabled", True):
        _log_step("Repo Local-Only Files Sync", "DISABLED", category=category)
        return

    click.echo("\nStep 8: Repo Local-Only Files Sync")
    
    profile_name = config.get('profile', 'default')
    project_id = config.get('project_id')
    bucket_name = config.get('bucket_name')

    # Perform Sync Configuration
    # We call configure_gcs_sync which handles dry_run internally.
    
    # Reload global config
    global_config, actual_global_config_file = _load_global_config()
    gcs_profile_manager = GCSProfileManager()
    
    # Get args from config if not passed
    arg_project_id = project_id
    arg_bucket_name = bucket_name
    
    updated_global_config, success, messages, error_message = gcs_profile_manager.configure_gcs_sync(arg_project_id, arg_bucket_name, profile_name, global_config, actual_global_config_file, dry_run)
    
    for msg in messages:
        click.echo(msg)

    if error_message:
        click.echo(f"❌ {error_message}", err=True)
        _log_step("Repo Local-Only Files Sync", "FAIL", error_message, category)
        sys.exit(1)
    elif success:
        # Determine status based on messages
        status = "VERIFIED"
        if dry_run:
            # If any message indicates a "Would" action (excluding verification checks), then we are READY (pending changes)
            # "Would verify" is a read-only check that is skipped in dry-run, but doesn't imply a pending write.
            pending_changes = [msg for msg in messages if "Would" in msg and "Would verify" not in msg and "Assuming bucket exists" not in msg]
            if pending_changes:
                status = "READY"
        else:
            # If we made changes (Labeled, Saved), then COMPLETED.
            # If we only verified existing state (Already labeled), then VERIFIED.
            # "Labeled" or "Saved" indicate action.
            if any("Labeled" in msg or "Saved" in msg or "GCS configured" in msg for msg in messages):
                 # Be careful, "Already labeled" contains "Labeled".
                 # Check for specific success actions or exclude "Already".
                 # "Project ... labeled" vs "Project ... is already labeled"
                 # "GCS configured" is the success message for saving config.
                 
                 # Let's look at specific action messages from GCSProfileManager:
                 # "Project ... labeled ..."
                 # "Bucket ... labeled ..."
                 # "GCS configured: ..."
                 
                 # And "Already" messages:
                 # "... is already labeled ..."
                 # "GCS configuration from global config ..."
                 
                 action_taken = False
                 for msg in messages:
                     if "labeled" in msg and "already" not in msg:
                         action_taken = True
                     if "GCS configured" in msg and "from global config" not in msg:
                         action_taken = True
                 
                 if action_taken:
                     status = "COMPLETED"

        _log_step("Repo Local-Only Files Sync", status, f"GCS configured for profile '{profile_name}'.", category)
    else:
        _log_step("Repo Local-Only Files Sync", "FAIL", f"Failed to configure GCS for profile '{profile_name}'.", category)
        sys.exit(1)
    click.echo("-" * 60)
