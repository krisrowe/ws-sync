#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 4: Overriding Global Config with Arguments ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_4"
echo "Setting up test directory: $TEST_DIR"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

set_common_test_env "$TEST_DIR"

# Ensure the temporary config file is clean
rm -f "$WS_SYNC_CONFIG"
# Ensure no existing .ws-sync file in the current directory
rm -f ".ws-sync"

# Identify project and bucket
identify_project_id
identify_bucket_name

# Ensure no labels are present on the project and bucket from previous runs
remove_gcs_labels "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME"

# Pre-configure the global config file with *different* values
echo "Pre-configuring global config file: $WS_SYNC_CONFIG with different values"
cat <<EOF > "$WS_SYNC_CONFIG"
gcs_profiles:
  default:
    project_id: "some-other-project"
    bucket_name: "some-other-bucket"
EOF

OVERRIDE_PROJECT_ID="$YOUR_TEST_PROJECT_ID"
OVERRIDE_BUCKET_NAME="$YOUR_TEST_BUCKET_NAME"

echo "Setup complete for Test Case 4."

# --- Execution ---
echo "Executing devws cli setup command with explicit arguments to override global config..."
(cd "$PROJECT_ROOT" && python3 -m devws_cli.cli setup --component proj_local_config_sync --project-id "$OVERRIDE_PROJECT_ID" --bucket-name "$OVERRIDE_BUCKET_NAME")

echo "Execution complete for Test Case 4."

# --- Verification ---
echo "Verifying results for Test Case 4..."

# Verify that the temporary config file ($WS_SYNC_CONFIG) is updated with the OVERRIDE_PROJECT_ID and OVERRIDE_BUCKET_NAME under the default profile.
echo "DEBUG: Verifying WS_SYNC_CONFIG: $WS_SYNC_CONFIG"
ls -l "$WS_SYNC_CONFIG"

if ! grep -q "project_id: $OVERRIDE_PROJECT_ID" "$WS_SYNC_CONFIG" || \
   ! grep -q "bucket_name: $OVERRIDE_BUCKET_NAME" "$WS_SYNC_CONFIG"; then
    echo "ERROR: Temporary config file ($WS_SYNC_CONFIG) does not contain expected project_id or bucket_name." >&2
    cat "$WS_SYNC_CONFIG" >&2
    exit 1
fi
echo "✅ Temporary config file ($WS_SYNC_CONFIG) contains expected project_id and bucket_name."

# Verify that the project and bucket are labeled ws-sync-test-case=default using OVERRIDE_PROJECT_ID and OVERRIDE_BUCKET_NAME.
if ! gcloud projects describe "$OVERRIDE_PROJECT_ID" --format="yaml(labels)" | grep -q "ws-sync-test-case: default"; then
    echo "ERROR: Project $OVERRIDE_PROJECT_ID is not labeled 'ws-sync-test-case: default'." >&2
    exit 1
fi
echo "✅ Project $OVERRIDE_PROJECT_ID is labeled 'ws-sync-test-case: default'."

echo "DEBUG: gsutil label get output for bucket gs://$OVERRIDE_BUCKET_NAME:"
gsutil label get "gs://$OVERRIDE_BUCKET_NAME"

if ! gsutil label get "gs://$OVERRIDE_BUCKET_NAME" | grep -q '"ws-sync-test-case": "default"'; then
    echo "ERROR: Bucket gs://$OVERRIDE_BUCKET_NAME is not labeled 'ws-sync-test-case: default'." >&2
    exit 1
fi
echo "✅ Bucket gs://$OVERRIDE_BUCKET_NAME is labeled 'ws-sync-test-case: default'."

echo "Verification complete for Test Case 4."

# --- Teardown ---
echo "Cleaning up Test Case 4..."
remove_gcs_labels "$OVERRIDE_PROJECT_ID" "$OVERRIDE_BUCKET_NAME"
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 4: PASSED ==="
