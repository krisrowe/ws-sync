import click
import os
import sys
import importlib
import traceback # For detailed error logging

from devws_cli.utils import (
    _log_step,
    _print_final_report,
    _load_config_from_repo,
    GLOBAL_DEVWS_CONFIG_FILE,
    GLOBAL_DEVWS_CONFIG_DIR,
    _load_global_config
)

# --- Global Definitions ---
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(REPO_DIR, '.git')) and REPO_DIR != os.path.dirname(REPO_DIR):
    REPO_DIR = os.path.dirname(REPO_DIR)
if not os.path.exists(os.path.join(REPO_DIR, '.git')):
    REPO_DIR = os.getcwd()

REPO_CONFIG_TEMPLATE_FILE = os.path.join(REPO_DIR, "config.yaml.example")

@click.command()
@click.option('--force', is_flag=True, help='Force re-run of setup steps.')
@click.option('--config-path', type=click.Path(exists=True), help='Path to a custom .config file.')
@click.option('--project-id', help='Google Cloud Project ID for GCS synchronization (overrides config).')
@click.option('--bucket-name', help='Google Cloud Storage bucket name for GCS synchronization (overrides config).')
@click.option('--profile', default='default', help='GCS profile name. Defaults to "default".')
@click.option('--component', multiple=True, help='Run only specified setup components (e.g., --component python --component github).')
def setup(force, config_path, project_id, bucket_name, profile, component):
    """
    Manages the Core Workstation Configuration setup.
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

    # Load global config (which might be empty or partially configured)
    global_config = _load_global_config()

    if not os.path.exists(GLOBAL_DEVWS_CONFIG_FILE):
        if os.path.exists(REPO_CONFIG_TEMPLATE_FILE):
            try:
                _run_command(['cp', REPO_CONFIG_TEMPLATE_FILE, GLOBAL_DEVWS_CONFIG_FILE])
                global_config = _load_global_config() # Reload after copy
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

    # --- Dynamic Component Loading and Execution ---
    components_config = repo_config.get("components", {})
    
    for component_name, component_settings in components_config.items():
        # Determine if component should run
        should_run = False
        if component: # If --component flag is used
            if component_name in component:
                should_run = True
            else:
                _log_step(f"{component_name.replace('_', ' ').title()} Setup", "DISABLED", f"Not specified with --component flag.")
                continue # Skip if not specified
        else: # If no --component flag, rely on config.yaml
            if component_settings.get("enabled", False):
                should_run = True
            else:
                _log_step(f"{component_name.replace('_', ' ').title()} Setup", "DISABLED", f"Disabled in config.yaml.")
                continue # Skip if disabled

        if should_run:
            try:
                # Dynamically import the component module
                component_module = importlib.import_module(f"devws_cli.components.{component_name}")
                
                # Prepare component-specific config
                current_component_config = component_settings.copy()

                # Handle overrides for proj_local_config_sync
                if component_name == "proj_local_config_sync":
                    if project_id:
                        current_component_config["project_id"] = project_id
                    if bucket_name:
                        current_component_config["bucket_name"] = bucket_name
                    current_component_config["profile"] = profile # Pass profile to component

                # Call the setup function in the component module
                component_module.setup(current_component_config)

            except ImportError:
                _log_step(f"{component_name.replace('_', ' ').title()} Setup", "FAIL", f"Component module '{component_name}' not found.")
                click.echo(f"Error: Component module '{component_name}' not found. Please check the component name and ensure the module exists in devws_cli/components.", err=True)
                sys.exit(1)
            except Exception as e:
                _log_step(f"{component_name.replace('_', ' ').title()} Setup", "FAIL", f"An error occurred: {e}")
                click.echo(f"Error running component '{component_name}': {e}", err=True)
                click.echo(traceback.format_exc(), err=True) # Print full traceback for debugging
                sys.exit(1)
    
    click.echo("-" * 60)

    # --- Final Report ---
    click.echo("\n" + "=" * 60)
    click.echo("SETUP COMPLETE!".center(60))
    click.echo("=" * 60)
    _print_final_report()