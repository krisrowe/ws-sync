#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 1: Auto-discovery of Labeled Resources ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_1"
echo "Setting up test directory: $TEST_DIR"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

set_common_test_env "$TEST_DIR"

# Ensure the temporary config file is clean
rm -rf "$WS_SYNC_CONFIG"
# Ensure no existing .ws-sync file in the current directory
rm -f ".ws-sync"

# Identify project and bucket
identify_project_id
identify_bucket_name

# Apply the ws-sync-test-case label to the GCP project and GCS bucket
apply_gcs_labels "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME"

echo "Setup complete for Test Case 1."

# --- Execution ---
echo "Executing devws cli setup command..."
(
    cd "$PROJECT_ROOT"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    echo "DEBUG: DEVWS_WS_SYNC_LABEL_KEY=$DEVWS_WS_SYNC_LABEL_KEY"
    echo "DEBUG: Running gcloud projects list check..."
    gcloud projects list --filter="labels.$DEVWS_WS_SYNC_LABEL_KEY=default" --format="value(project_id)"
    python3 -m devws_cli.cli setup --component proj_local_config_sync
)

echo "Execution complete for Test Case 1."

# --- Verification ---
echo "Verifying results for Test Case 1..."

echo "DEBUG: Verifying WS_SYNC_CONFIG: $WS_SYNC_CONFIG"
ls -l "$WS_SYNC_CONFIG_FILE"

# Verify that the temporary config file ($WS_SYNC_CONFIG) is created and contains the project_id and bucket_name under the default profile.
if ! grep -q "project_id: $YOUR_TEST_PROJECT_ID" "$WS_SYNC_CONFIG_FILE" || \
   ! grep -q "bucket_name: $YOUR_TEST_BUCKET_NAME" "$WS_SYNC_CONFIG_FILE"; then
    echo "ERROR: Temporary config file ($WS_SYNC_CONFIG) does not contain expected project_id or bucket_name." >&2
    cat "$WS_SYNC_CONFIG_FILE" >&2
    exit 1
fi
echo "✅ Temporary config file ($WS_SYNC_CONFIG) contains expected project_id and bucket_name."

# Verify that the project and bucket are labeled ws-sync-test-case=default.
if ! gcloud projects describe "$YOUR_TEST_PROJECT_ID" --format="yaml(labels)" | grep -q "ws-sync-test-case: default"; then
    echo "ERROR: Project $YOUR_TEST_PROJECT_ID is not labeled 'ws-sync-test-case: default'." >&2
    exit 1
fi
echo "✅ Project $YOUR_TEST_PROJECT_ID is labeled 'ws-sync-test-case: default'."

echo "DEBUG: gsutil label get output for bucket gs://$YOUR_TEST_BUCKET_NAME:"
gsutil label get "gs://$YOUR_TEST_BUCKET_NAME"

if ! gsutil label get "gs://$YOUR_TEST_BUCKET_NAME" | grep -q '"ws-sync-test-case": "default"'; then
    echo "ERROR: Bucket gs://$YOUR_TEST_BUCKET_NAME is not labeled 'ws-sync-test-case: default'." >&2
    exit 1
fi
echo "✅ Bucket gs://$YOUR_TEST_BUCKET_NAME is labeled 'ws-sync-test-case: default'."

echo "Verification complete for Test Case 1."

# --- Teardown ---
echo "Cleaning up Test Case 1..."
remove_gcs_labels "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME"
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 1: PASSED ==="
