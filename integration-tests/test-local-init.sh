#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 7: Test devws local init (no .ws-sync file) ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_7"
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

# Configure GCS test profile using the common function
configure_gcs_test_config "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME" "$WS_SYNC_CONFIG"

# Ensure no .ws-sync file exists
rm -f ".ws-sync"

echo "Setup complete for Test Case 7."

# --- Execution ---
echo "Executing devws cli local init command..."
(cd "$PROJECT_ROOT" && python3 -m devws_cli.cli local init)

echo "Execution complete for Test Case 7."

# --- Verification ---
echo "Verifying results for Test Case 7..."

# Verify that a .ws-sync file is created
if [ ! -f ".ws-sync" ]; then
    echo "ERROR: .ws-sync file was not created." >&2
    exit 1
fi
echo "✅ .ws-sync file was created."

# Verify that the .ws-sync file contains default content or a header
if ! grep -q "# This file specifies project-specific files that should be synchronized" .ws-sync; then
    echo "ERROR: .ws-sync file does not contain the expected default header." >&2
    cat .ws-sync >&2
    exit 1
fi
echo "✅ .ws-sync file contains the expected default header."

echo "Verification complete for Test Case 7."

# --- Teardown ---
echo "Cleaning up Test Case 7..."
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 7: PASSED ==="
