import os
import json
import yaml
import subprocess
import click # Import click for echo
from devws_cli.utils import _run_command, _get_ws_sync_label_key, _load_global_config, GLOBAL_DEVWS_CONFIG_FILE

class GCSProfileManager:
    def __init__(self, silent=False, debug=False):
        self.silent = silent
        self.debug = debug

    def _apply_label_to_project(self, project_id, profile_name):
        """Applies ws-sync label to a project."""
        label_key = _get_ws_sync_label_key()
        try:
            _run_command(['gcloud', 'alpha', 'projects', 'update', project_id, f'--update-labels={label_key}={profile_name}'], check=True)
            return True
        except Exception:
            return False

    def _remove_label_from_project(self, project_id, profile_name):
        """Removes ws-sync label from a project."""
        label_key = _get_ws_sync_label_key()
        try:
            _run_command(['gcloud', 'alpha', 'projects', 'update', project_id, f'--remove-labels={label_key}'], check=True)
            return True
        except Exception:
            return False

    def _apply_label_to_bucket(self, bucket_name, profile_name):
        """Applies ws-sync label to a bucket."""
        label_key = _get_ws_sync_label_key()
        try:
            _run_command(['gsutil', 'label', 'ch', '-l', f'{label_key}:{profile_name}', f'gs://{bucket_name}'], check=True)
            return True
        except Exception:
            return False

    def _remove_label_from_bucket(self, bucket_name, profile_name):
        """Removes ws-sync label from a bucket."""
        label_key = _get_ws_sync_label_key()
        try:
            _run_command(['gsutil', 'label', 'ch', '-d', f'{label_key}', f'gs://{bucket_name}'], check=True)
            return True
        except Exception:
            return False

    def _get_project_id_from_bucket(self, bucket_name):
        """
        Attempts to get the project ID that owns a given bucket.
        """
        try:
            desc_output = _run_command(['gcloud', 'storage', 'buckets', 'describe', f'gs://{bucket_name}', '--format=json'], capture_output=True, check=False).stdout
            if desc_output:
                bucket_info = json.loads(desc_output)
                project_id = bucket_info.get('project')
                if project_id:
                    return project_id
                
                project_number = bucket_info.get('projectNumber')
                if project_number:
                    projects_output = _run_command(['gcloud', 'projects', 'list', f'--filter=projectNumber={project_number}', '--format=value(projectId)'], capture_output=True, check=False).stdout
                    if projects_output:
                        return projects_output.strip()

        except Exception:
            pass # Ignore errors, return None
        return None

    def _find_labeled_gcs_resources(self, profile_name):
        """
        Finds GCP projects and GCS buckets labeled with the given profile name.
        Returns (list_of_project_ids, list_of_bucket_names).
        """
        label_key = _get_ws_sync_label_key()
        
        # Find labeled projects
        projects_output = _run_command(['gcloud', 'projects', 'list', f'--filter=labels.{label_key}={profile_name}', '--format=value(project_id)'], capture_output=True).stdout
        labeled_projects = [p.strip() for p in projects_output.splitlines() if p.strip()]

        # Find labeled buckets
        labeled_buckets = []
        try:
            # Get the project ID from the identified labeled projects, or from gcloud config
            # This is a heuristic, as a bucket might be labeled but not its project.
            # For now, we'll try to list buckets in the identified project.
            target_project_id = labeled_projects[0] if labeled_projects else _run_command(['gcloud', 'config', 'get-value', 'project'], capture_output=True).stdout.strip()

            if not target_project_id:
                return labeled_projects, labeled_buckets

            all_buckets_output = _run_command(['gsutil', 'ls', '-p', target_project_id], capture_output=True).stdout
            for bucket_uri in all_buckets_output.splitlines():
                if bucket_uri.startswith('gs://'):
                    bucket_name = bucket_uri.replace('gs://', '').replace('/', '')
                    try:
                        bucket_labels_output = _run_command(['gsutil', 'label', 'get', bucket_uri], capture_output=True, check=False).stdout
                        
                        bucket_labels = {}
                        if "has no label configuration" not in bucket_labels_output:
                            parsed_labels = yaml.safe_load(bucket_labels_output)
                            if isinstance(parsed_labels, dict):
                                bucket_labels = parsed_labels
                        
                        if bucket_labels.get(label_key) == profile_name:
                            labeled_buckets.append(bucket_name)
                    except Exception:
                        pass
        except Exception:
            pass
        
        return labeled_projects, labeled_buckets
    
    def configure_gcs_sync(self, arg_project_id, arg_bucket_name, profile_name, global_config_dict, actual_global_config_file, dry_run=False):
        """
        Core logic for GCS synchronization configuration, non-CLI-aware.
        Takes arguments and current global config dictionary.
        Returns (updated_global_config_dict, success_status, messages_list, error_message).
        """
        messages = []
        error_message = None
        success = False

        # Ensure gcs_profiles exists in the global config
        if 'gcs_profiles' not in global_config_dict:
            global_config_dict['gcs_profiles'] = {}
        
        # Get current state from global config file for the specific profile (if any)
        profile_config = global_config_dict['gcs_profiles'].get(profile_name, {})
        config_project_id = profile_config.get('project_id')
        config_bucket_name = profile_config.get('bucket_name')

        chosen_project_id = arg_project_id
        chosen_bucket_name = arg_bucket_name
        
        # Check for GCS CLI and authentication before proceeding
        if _run_command(['which', 'gcloud'], capture_output=True, check=False).returncode != 0:
            error_message = "Google Cloud CLI not found. Please install it first."
            return global_config_dict, False, messages, error_message
        if _run_command(['gcloud', 'auth', 'list'], capture_output=True, check=False).returncode != 0:
            error_message = "Not authenticated with Google Cloud. Please run 'gcloud auth login' and try again."
            return global_config_dict, False, messages, error_message

        # --- Determine project_id and bucket_name ---
        # If arguments were provided, they take precedence
        if chosen_project_id or chosen_bucket_name:
            # If args are provided, and there's an existing config, but the args are different,
            # we should still proceed with the args, but maybe issue a warning if it's a significant change.
            # For now, we'll let args override silently.
            pass
        else: # No arguments provided, try to derive from config or labels
            if config_project_id and config_bucket_name:
                messages.append(f"ℹ️ GCS configuration from global config: Project ID='{config_project_id}', Bucket='{config_bucket_name}' for profile '{profile_name}'.")
                chosen_project_id = config_project_id
                chosen_bucket_name = config_bucket_name
            else:
                # Try to derive from labeled resources
                labeled_projects, labeled_buckets = self._find_labeled_gcs_resources(profile_name)
                
                # Filter labeled buckets to only those within labeled projects, and get unique (project_id, bucket_name)
                found_gcp_setups = set()
                for p_id_label in labeled_projects:
                    for b_name_label in labeled_buckets:
                        found_gcp_setups.add((p_id_label, b_name_label))
                
                if len(found_gcp_setups) == 1:
                    derived_project_id, derived_bucket_name = list(found_gcp_setups)[0]
                    messages.append(f"ℹ️ Derived GCS configuration from existing labels: Project ID='{derived_project_id}', Bucket='{derived_bucket_name}' for profile '{profile_name}'.")
                    chosen_project_id = derived_project_id
                    chosen_bucket_name = derived_bucket_name
                elif len(found_gcp_setups) > 1:
                    error_message = f"Ambiguous GCS setup for profile '{profile_name}'. Found multiple or partial labeled resources:\n"
                    if labeled_projects:
                        error_message += f"   Labeled Projects: {', '.join(labeled_projects)}\n"
                    if labeled_buckets:
                        error_message += f"   Labeled Buckets: {', '.join(labeled_buckets)}\n"
                    error_message += "Please manually resolve the ambiguity by specifying --project-id and --bucket-name, or by clearing labels with 'gcloud/gsutil label ch -d " + _get_ws_sync_label_key() + " ...'."
                    return global_config_dict, False, messages, error_message
                else:
                    error_message = f"No GCS configuration found or derivable for profile '{profile_name}'. Please provide --project-id and --bucket-name arguments."
                    return global_config_dict, False, messages, error_message

        # Final check before proceeding with chosen values
        if not chosen_project_id or not chosen_bucket_name:
            error_message = "Project ID and Bucket Name are required for GCS configuration. Provide them as arguments or when prompted."
            return global_config_dict, False, messages, error_message

        # Validation: Verify Bucket exists in Project
        if dry_run:
            messages.append(f"🔍 [DRY RUN] Would verify bucket 'gs://{chosen_bucket_name}' exists in project '{chosen_project_id}'")
            messages.append(f"🔍 [DRY RUN] Assuming bucket exists for dry-run")
        else:
            messages.append(f"ℹ️ Verifying if bucket 'gs://{chosen_bucket_name}' exists in project '{chosen_project_id}'...")
            try:
                _run_command(['gsutil', 'ls', '-p', chosen_project_id, f'gs://{chosen_bucket_name}'], capture_output=True, check=True)
                messages.append(f"✅ Bucket 'gs://{chosen_bucket_name}' found in project '{chosen_project_id}'.")
            except Exception as e:
                error_message = f"Bucket 'gs://{chosen_bucket_name}' not found in project '{chosen_project_id}' or you don't have permissions: {e}\n"
                error_message += "Please ensure the bucket name and project ID are correct and you have appropriate permissions."
                return global_config_dict, False, messages, error_message
        
        # Validation: Check for existing labels before applying
        # Project labels
        try:
            project_labels_output = _run_command(['gcloud', 'projects', 'describe', chosen_project_id, '--format=yaml(labels)'], capture_output=True, check=False).stdout
            project_labels = yaml.safe_load(project_labels_output).get('labels', {})
            label_key = _get_ws_sync_label_key()
            if project_labels.get(label_key) and project_labels.get(label_key) != profile_name:
                error_message = f"Project '{chosen_project_id}' is already labeled '{label_key}={project_labels.get(label_key)}' (different profile).\n"
                error_message += f"   To proceed, please remove the existing label using: gcloud projects update {chosen_project_id} --remove-labels={label_key}"
                return global_config_dict, False, messages, error_message
            if project_labels.get(label_key) == profile_name:
                messages.append(f"✅ Project '{chosen_project_id}' is already labeled '{label_key}={profile_name}'.")
            else: # Apply label if not present
                if dry_run:
                    messages.append(f"🔍 [DRY RUN] Would label project '{chosen_project_id}' with '{label_key}={profile_name}'")
                else:
                    if not self._apply_label_to_project(chosen_project_id, profile_name):
                        error_message = f"Failed to apply label '{label_key}={profile_name}' to project '{chosen_project_id}'."
                        return global_config_dict, False, messages, error_message
                    messages.append(f"✅ Project '{chosen_project_id}' labeled '{label_key}={profile_name}'.")
        except Exception as e:
            error_message = f"Could not check/label project '{chosen_project_id}': {e}"
            return global_config_dict, False, messages, error_message

        # Bucket labels
        try:
            bucket_labels_output = _run_command(['gsutil', 'label', 'get', f'gs://{chosen_bucket_name}'], capture_output=True, check=False).stdout
            bucket_labels = {}
            for line in bucket_labels_output.splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    bucket_labels[k.strip()] = v.strip()
            
            label_key = _get_ws_sync_label_key()
            if bucket_labels.get(label_key) and bucket_labels.get(label_key) != profile_name:
                error_message = f"Bucket 'gs://{chosen_bucket_name}' is already labeled '{label_key}={bucket_labels.get(label_key)}' (different profile).\n"
                error_message += f"   To proceed, please remove the existing label using: gsutil label ch -d {label_key} gs://{chosen_bucket_name}"
                return global_config_dict, False, messages, error_message
            if bucket_labels.get(label_key) == profile_name:
                messages.append(f"✅ Bucket 'gs://{chosen_bucket_name}' is already labeled '{label_key}={profile_name}'.")
            else: # Apply label if not present
                if dry_run:
                    messages.append(f"🔍 [DRY RUN] Would label bucket 'gs://{chosen_bucket_name}' with '{label_key}={profile_name}'")
                else:
                    if not self._apply_label_to_bucket(chosen_bucket_name, profile_name):
                        error_message = f"Failed to apply label '{label_key}={profile_name}' to bucket 'gs://{chosen_bucket_name}'."
                        return global_config_dict, False, messages, error_message
                    messages.append(f"✅ Bucket 'gs://{chosen_bucket_name}' labeled '{label_key}={profile_name}'.")
        except Exception as e:
            error_message = f"Could not check/label bucket 'gs://{chosen_bucket_name}': {e}"
            return global_config_dict, False, messages, error_message

        # Store in global config
        if dry_run:
            messages.append(f"🔍 [DRY RUN] Would save to config: Project ID='{chosen_project_id}', Bucket='{chosen_bucket_name}' to {actual_global_config_file}")
            success = True
        else:
            global_config_dict['gcs_profiles'][profile_name] = {
                'project_id': chosen_project_id,
                'bucket_name': chosen_bucket_name
            }

            try:
                with open(actual_global_config_file, 'w') as f:
                    yaml.safe_dump(global_config_dict, f, default_flow_style=False)
                messages.append(f"✅ GCS configured: Project ID='{chosen_project_id}', Bucket='{chosen_bucket_name}' saved to {actual_global_config_file}")
                success = True
            except IOError as e:
                error_message = f"Error writing to global config file {actual_global_config_file}: {e}"
                success = False

        return global_config_dict, success, messages, error_message
