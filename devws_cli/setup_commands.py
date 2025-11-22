import click
import os
import sys
import yaml
import importlib
import traceback

from devws_cli.utils import (
    _log_step,
    _print_final_report,
    _load_config_from_repo,
    GLOBAL_DEVWS_CONFIG_FILE,
    GLOBAL_DEVWS_CONFIG_DIR,
    _load_global_config,
    _run_command,  # Add missing import
    get_gcs_profile_config # New: Import get_gcs_profile_config
)
from devws_cli.gcs_manager import GCSManager # New: Import GCSManager
from devws_cli.gcs_profile_manager import GCSProfileManager # New: Import GCSProfileManager

# --- Global Definitions ---
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(REPO_DIR, '.git')) and REPO_DIR != os.path.dirname(REPO_DIR):
    REPO_DIR = os.path.dirname(REPO_DIR)
if not os.path.exists(os.path.join(REPO_DIR, '.git')):
    REPO_DIR = os.getcwd()

REPO_CONFIG_TEMPLATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.default.yaml")

@click.command()
@click.option('--force', is_flag=True, help='Force re-run of setup steps.')
@click.option('--config-path', type=click.Path(exists=True), help='Path to a custom config.yaml file.')
@click.option('--project-id', help='Google Cloud Project ID for GCS synchronization (overrides config).')
@click.option('--bucket-name', help='Google Cloud Storage bucket name for GCS synchronization (overrides config).')
@click.option('--profile', default='default', help='GCS profile name. Defaults to "default".')
@click.option('--component', multiple=True, help='Run only specified setup components (e.g., --component python --component github).')
@click.option('--dry-run', is_flag=True, help='Simulate the setup process without making any changes.')
def setup(force, config_path, project_id, bucket_name, profile, component, dry_run):
    """
    Initializes or updates the core workstation configuration.

    This command installs and configures essential development tools,
    language runtimes, and CLI utilities. It is idempotent, meaning
    it can be run multiple times safely.
    """
    click.echo("=" * 60)
    click.echo("Starting ChromeOS Development Environment Setup".center(60))
    click.echo(f"Repository (determined): {REPO_DIR}".center(60))
    click.echo("-" * 60)

    # Load configuration
    repo_config = _load_config_from_repo(REPO_DIR)

    # --- Step 0: Initializing Global devws Configuration ---
    click.echo("\nStep 0: Initializing Global devws Configuration")
    if not os.path.exists(GLOBAL_DEVWS_CONFIG_DIR):
        os.makedirs(GLOBAL_DEVWS_CONFIG_DIR)
        _log_step("Global Config Directory", "COMPLETED", f"Created {GLOBAL_DEVWS_CONFIG_DIR}")
    else:
        _log_step("Global Config Directory", "VERIFIED", f"{GLOBAL_DEVWS_CONFIG_DIR} already exists.")

    global_config, _ = _load_global_config()

    if not os.path.exists(GLOBAL_DEVWS_CONFIG_FILE):
        if os.path.exists(REPO_CONFIG_TEMPLATE_FILE):
            try:
                _run_command(['cp', REPO_CONFIG_TEMPLATE_FILE, GLOBAL_DEVWS_CONFIG_FILE])
                global_config, _ = _load_global_config()
                _log_step("Global Config File", "COMPLETED", f"Copied {REPO_CONFIG_TEMPLATE_FILE} to {GLOBAL_DEVWS_CONFIG_FILE}")
                click.echo(f"ℹ️ Please review and customize your global devws configuration at {GLOBAL_DEVWS_CONFIG_FILE}")
            except Exception as e:
                _log_step("Global Config File", "FAIL", f"Failed to copy example config to {GLOBAL_DEVWS_CONFIG_FILE}: {e}")
        else:
            try:
                with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
                    yaml.safe_dump(global_config, f, default_flow_style=False)
                _log_step("Global Config File", "COMPLETED", f"Created default {GLOBAL_DEVWS_CONFIG_FILE}")
                click.echo(f"ℹ️ Please review and customize your global devws configuration at {GLOBAL_DEVWS_CONFIG_FILE}")
            except IOError as e:
                _log_step("Global Config File", "FAIL", f"Failed to create {GLOBAL_DEVWS_CONFIG_FILE}: {e}")
    else:
        _log_step("Global Config File", "VERIFIED", f"{GLOBAL_DEVWS_CONFIG_FILE} already exists.")
    click.echo("-" * 60)

    # --- Step 1: GCS Path Migration (if needed) ---
    click.echo("\nStep 1: Checking for old GCS path structure for migration...")
    _migrate_old_gcs_paths(global_config, force) # Pass global_config and force
    click.echo("-" * 60)

    # --- Consolidate and Sort Components by Tier ---
    all_components_to_run = []

    # Add built-in components
    components_config = repo_config.get("components", {})
    for comp_id, comp_settings in components_config.items():
        all_components_to_run.append({
            "id": comp_id,
            "name": comp_id.replace('_', ' ').title(),
            "type": "builtin",
            "settings": comp_settings,
            "tier": comp_settings.get("tier", 2) # Default tier 2 for built-in
        })
    
    # Add custom components
    custom_components = repo_config.get("custom_components", [])
    for comp in custom_components:
        all_components_to_run.append({
            "id": comp.get("id"),
            "name": comp.get("name", comp.get("id")),
            "type": "custom",
            "settings": comp,
            "tier": comp.get("tier", 3) # Default tier 3 for custom
        })
    
    # Sort components by tier
    all_components_to_run.sort(key=lambda x: x["tier"])

    click.echo("\n--- Running Setup Components by Tier ---")
    
    # Initialize GCSManager if a bucket is configured for custom components
    profile_name = global_config.get('default_gcs_profile', 'default') # Get from updated global_config
    project_id, bucket_name = get_gcs_profile_config(profile_name)
    gcs_manager = None
    if bucket_name:
        gcs_manager = GCSManager(bucket_name, profile_name=profile_name)
    
    for comp_data in all_components_to_run:
        comp_id = comp_data["id"]
        comp_name = comp_data["name"]
        comp_type = comp_data["type"]
        comp_settings = comp_data["settings"]
        comp_tier = comp_data["tier"]

        # Determine if component should run based on --component flag and 'enabled' setting
        should_run = False
        if component: # If --component flag is used
            if comp_id in component:
                should_run = True
            else:
                _log_step(f"({comp_tier}) {comp_name} Setup", "DISABLED", f"Not specified with --component flag.")
                continue # Skip if not specified
        else: # If no --component flag, rely on config.yaml 'enabled' setting
            if comp_settings.get("enabled", False):
                should_run = True
            else:
                _log_step(f"({comp_tier}) {comp_name} Setup", "DISABLED", f"Disabled in config.yaml.")
                continue # Skip if disabled

        if should_run:
            if comp_type == "builtin":
                try:
                    # Dynamically import the component module
                    component_module = importlib.import_module(f"devws_cli.components.{comp_id}")
                    
                    # Prepare component-specific config
                    current_component_config = comp_settings.copy()

                    # Handle overrides for proj_local_config_sync
                    if comp_id == "proj_local_config_sync":
                        if project_id:
                            current_component_config["project_id"] = project_id
                        if bucket_name:
                            current_component_config["bucket_name"] = bucket_name
                        current_component_config["profile"] = profile # Pass profile to component

                    # Call the setup function in the component module
                    component_module.setup(current_component_config)

                except ImportError:
                    _log_step(f"({comp_tier}) {comp_name} Setup", "FAIL", f"Component module '{comp_id}' not found.")
                    click.echo(f"Error: Component module '{comp_id}' not found. Please check the component name and ensure the module exists in devws_cli/components.", err=True)
                    sys.exit(1)
                except Exception as e:
                    _log_step(f"({comp_tier}) {comp_name} Setup", "FAIL", f"An error occurred: {e}")
                    click.echo(f"Error running component '{comp_id}': {e}", err=True)
                    click.echo(traceback.format_exc(), err=True) # Print full traceback for debugging
                    sys.exit(1)
            elif comp_type == "custom":
                comp_description = comp_settings.get("description", "No description provided.")
                comp_idempotent_check = comp_settings.get("idempotent_check")
                comp_on_failure = comp_settings.get("on_failure", "continue")

                # Idempotency Check
                if comp_idempotent_check:
                    try:
                        result = _run_command(comp_idempotent_check, shell=True, capture_output=True, check=False)
                        if result.returncode == 0:
                            _log_step(f"({comp_tier}) Custom Component: {comp_name}", "VERIFIED", "Idempotency check passed (already done).")
                            continue
                    except Exception as e:
                        _log_step(f"({comp_tier}) Custom Component: {comp_name}", "FAIL", f"Idempotency check failed: {e}")
                        if comp_on_failure == "abort":
                            sys.exit(1)
                        continue
                
                # Execute Custom Component
                if not gcs_manager:
                    _log_step(f"({comp_tier}) Custom Component: {comp_name}", "FAIL", "GCS Manager not initialized. Cannot fetch script.")
                    if comp_on_failure == "abort":
                        sys.exit(1)
                    continue

                script_gcs_path = os.path.join(gcs_manager.get_user_components_gcs_path(), f"{comp_id}.sh")
                temp_script_path = os.path.join(GLOBAL_DEVWS_CONFIG_DIR, f"{comp_id}.sh") # Use GLOBAL_DEVWS_CONFIG_DIR for temp

                try:
                    # Download script
                    click.echo(f"ℹ️ Downloading custom component '{comp_name}' script from GCS...")
                    gcs_manager.gcs_cp(script_gcs_path, temp_script_path, debug=True)
                    os.chmod(temp_script_path, 0o755) # Make executable

                    # Execute script
                    _log_step(f"({comp_tier}) Custom Component: {comp_name}", "COMPLETED", f"Executing: {comp_description}")
                    result = _run_command(temp_script_path, shell=True, check=False) # check=False to handle script's own exit code
                    if result.returncode == 0:
                        _log_step(f"({comp_tier}) Custom Component: {comp_name}", "PASS")
                    else:
                        _log_step(f"({comp_tier}) Custom Component: {comp_name}", "FAIL", f"Script exited with code {result.returncode}")
                        if result.stdout: click.echo(f"Stdout: {result.stdout}")
                        if result.stderr: click.echo(f"Stderr: {result.stderr}")
                        if comp_on_failure == "abort":
                            sys.exit(1)
                except Exception as e:
                    _log_step(f"({comp_tier}) Custom Component: {comp_name}", "FAIL", f"An error occurred: {e}")
                    click.echo(traceback.format_exc(), err=True)
                    if comp_on_failure == "abort":
                        sys.exit(1)
                finally:
                    # Clean up temporary script
                    if os.path.exists(temp_script_path):
                        os.remove(temp_script_path)
    
    click.echo("-" * 60)

    # --- Final Report ---
    click.echo("\n" + "=" * 60)

    # --- Final Report ---
    click.echo("\n" + "=" * 60)
    click.echo("SETUP COMPLETE!".center(60))
    click.echo("=" * 60)
    _print_final_report()

def _migrate_old_gcs_paths(global_config, force_migration):
    """
    Migrates GCS objects from the old '/projects/<owner>/<repo>' path to the new '/repos/<owner>/<repo>' path.
    """
    migration_completed_key = 'gcs_migration_v1_completed'
    if global_config.get(migration_completed_key) and not force_migration:
        _log_step("GCS Path Migration", "VERIFIED", "Migration already completed.")
        return

    profile_name = global_config.get('default_gcs_profile', 'default')
    project_id, bucket_name = get_gcs_profile_config(profile_name)

    if not bucket_name:
        _log_step("GCS Path Migration", "SKIP", "No GCS bucket configured.")
        return

    gcs_manager = GCSManager(bucket_name, profile_name=profile_name)
    base_gcs_url = gcs_manager.bucket_url

    old_prefix = f"{base_gcs_url}/projects/"
    new_prefix = f"{base_gcs_url}/repos/"

    try:
        # List all objects under the old /projects/ prefix
        click.echo(f"ℹ️ Listing objects under old GCS path: {old_prefix}")
        old_paths = gcs_manager.gcs_ls(f"{old_prefix}*", recursive=True, debug=True) # List all sub-objects

        if not old_paths:
            _log_step("GCS Path Migration", "VERIFIED", "No old GCS paths found for migration.")
        else:
            _log_step("GCS Path Migration", "COMPLETED", "Starting migration of old GCS paths.")
            migrated_count = 0
            for old_path in old_paths:
                # Example old_path: gs://my-bucket/projects/owner/repo/file.txt
                # Need to extract 'owner/repo/file.txt' part
                relative_path = old_path.replace(old_prefix, '')
                
                # Construct new path: gs://my-bucket/repos/owner/repo/file.txt
                new_path = f"{new_prefix}{relative_path}"
                
                click.echo(f"Moving {old_path} to {new_path}")
                gcs_manager.gcs_mv(old_path, new_path, debug=True)
                migrated_count += 1
            
            _log_step("GCS Path Migration", "COMPLETED", f"Migrated {migrated_count} objects.")

        # Mark migration as completed in global config
        global_config[migration_completed_key] = True
        with open(GLOBAL_DEVWS_CONFIG_FILE, 'w') as f:
            yaml.safe_dump(global_config, f, default_flow_style=False)
        
    except Exception as e:
        _log_step("GCS Path Migration", "FAIL", f"Error during migration: {e}")