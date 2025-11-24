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
@click.option('--component', multiple=True, help='Run only specified setup components (e.g., --component python).')
@click.option('--dry-run', is_flag=True, help='Simulate the setup process without making any changes.')
def setup(force, config_path, project_id, bucket_name, profile, component, dry_run):
    """
    Initializes or updates the core workstation configuration based on the global config file.
    """
    click.echo("=" * 60)
    if dry_run:
        click.echo("🔍 DRY RUN MODE - No changes will be made".center(60))
        click.echo("=" * 60)
    click.echo("Starting ChromeOS Development Environment Setup".center(60))
    click.echo(f"Repository (determined): {REPO_DIR}".center(60))
    click.echo("-" * 60)

    # --- Pre-requisite Check for Global Config ---
    # The _load_global_config now merges base and user configs, so this just checks existence of user's config
    if not os.path.exists(GLOBAL_DEVWS_CONFIG_FILE):
        click.echo(f"❌ Global config file not found at '{GLOBAL_DEVWS_CONFIG_FILE}'.", err=True)
        click.echo("   Please run 'devws config init' for a new setup, or 'devws config restore' to sync from GCS.", err=True)
        sys.exit(1)

    # Load combined configuration (base + user)
    global_config_dict, actual_global_config_file = _load_global_config()

    # --- Consolidate and Sort Components by Category and Tier ---
    all_components = []
    if "components" in global_config_dict:
        for comp_id, comp_settings in global_config_dict["components"].items():
            all_components.append({
                "id": comp_id,
                "name": comp_settings.get("name", comp_id.replace('_', ' ').title()),
                "settings": comp_settings,
                "tier": comp_settings.get("tier", 2), # Default tier 2
                "category": comp_settings.get("category", "custom") # Default category custom
            })
    
    # Sort by category priority (core, common, development, custom), then by tier
    category_order = {"core": 0, "common": 1, "development": 2, "custom": 3}
    all_components.sort(key=lambda x: (category_order.get(x["category"], 999), x["tier"]))

    click.echo("\n--- Running Setup Components by Category ---")

    # --- Setup Custom Component Path ---
    custom_components_dir = os.path.join(GLOBAL_DEVWS_CONFIG_DIR, "components")
    if not os.path.isdir(custom_components_dir):
        if not dry_run: os.makedirs(custom_components_dir, exist_ok=True)
    
    # Add custom components path to sys.path for dynamic importing
    # This ensures that custom component modules can be imported directly by their name
    if custom_components_dir not in sys.path:
        sys.path.insert(0, custom_components_dir)
    
    for comp_data in all_components:
        comp_id = comp_data["id"]
        comp_name = comp_data["name"]
        comp_settings = comp_data["settings"]
        comp_tier = comp_data["tier"]
        comp_category = comp_data["category"]

        # Filter by --component flag
        if component and comp_id not in component:
            _log_step(f"{comp_name} Setup", "DISABLED", "Not specified via --component flag.", comp_category)
            continue
        
        # Check if enabled in config
        if not comp_settings.get("enabled", False):
            _log_step(f"{comp_name} Setup", "DISABLED", "Disabled in config.", comp_category)
            continue

        # Determine if already done (idempotency check)
        is_done = False
        if comp_settings.get("idempotent_check"):
            try:
                # Idempotency check should always run, even in dry-run mode, to determine status
                # Pass dry_run=False here as idempotent checks MUST execute
                result = _run_command(comp_settings["idempotent_check"], shell=True, capture_output=True, check=False, dry_run=False, is_idempotent_check=True)
                if result.returncode == 0:
                    _log_step(f"{comp_name} Setup", "VERIFIED", "Idempotency check passed (already done).", comp_category)
                    is_done = True
            except Exception as e:
                _log_step(f"{comp_name} Setup", "FAIL", f"Idempotency check failed: {e}", comp_category)
                click.echo(traceback.format_exc(), err=True)
                # If idempotent check fails, and on_failure is 'abort', exit
                if comp_settings.get("on_failure", "continue") == "abort":
                    sys.exit(1)
                continue # Skip further execution of this component
        
        if is_done:
            continue # Already verified, move to next component

        # Dynamically import and execute the component
        try:
            component_module = None
            try:
                # Try importing as a built-in component
                component_module = importlib.import_module(f"devws_cli.components.{comp_id}")
            except ImportError:
                try:
                    # If that fails, try importing from the custom components directory
                    # The custom module name is just the comp_id (e.g., 'google_bugged')
                    component_module = importlib.import_module(comp_id)
                except ImportError:
                    _log_step(f"{comp_name} Setup", "FAIL", f"Component module '{comp_id}.py' not found in built-in or custom paths.", comp_category)
                    click.echo(f"Error: Component module '{comp_id}.py' not found. Ensure it exists and is correctly named in '{custom_components_dir}'.", err=True)
                    if comp_settings.get("on_failure", "continue") == "abort":
                        sys.exit(1)
                    continue

            # Call the setup function with the component's config and dry_run flag
            if hasattr(component_module, 'setup'):
                component_module.setup(comp_settings, dry_run=dry_run)
                # The component's setup function is responsible for calling _log_step
            else:
                _log_step(f"{comp_name} Setup", "FAIL", "No setup() function found in component.", comp_category)

        except Exception as e:
            _log_step(f"{comp_name} Setup", "FAIL", f"An error occurred during execution: {e}", comp_category)
            click.echo(traceback.format_exc(), err=True)
            if comp_settings.get("on_failure", "continue") == "abort":
                sys.exit(1)
    
    # Clean up sys.path
    if custom_components_dir in sys.path:
        sys.path.remove(custom_components_dir)

    click.echo("-" * 60)
    click.echo("\n" + "=" * 60)
    click.echo("SETUP COMPLETE!".center(60))
    click.echo("=" * 60)
    _print_final_report()