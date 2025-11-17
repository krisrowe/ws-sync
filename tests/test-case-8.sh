#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 8: Test devws local init (with existing .ws-sync file) ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_8"
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

# Pre-configure the global config file with test resources
echo "Pre-configuring global config file: $WS_SYNC_CONFIG"
cat <<EOF > "$WS_SYNC_CONFIG"
gcs_profiles:
  default:
    project_id: "$YOUR_TEST_PROJECT_ID"
    bucket_name: "$YOUR_TEST_BUCKET_NAME"
EOF

# Create an existing .ws-sync file with some content
echo "Creating existing .ws-sync file..."
echo "existing_content.txt" > .ws-sync
EXPECTED_WS_SYNC_CONTENT=$(cat .ws-sync)

echo "Setup complete for Test Case 8."

# --- Execution ---
echo "Executing devws cli local init command..."
set +e # Temporarily disable exit on error
OUTPUT=$( (cd "$PROJECT_ROOT" && python3 -m devws_cli.cli local init) 2>&1 )
EXIT_CODE=$?
set -e # Re-enable exit on error

echo "Execution complete for Test Case 8."

# --- Verification ---
echo "Verifying results for Test Case 8..."

# Verify that a message is displayed indicating that .ws-sync already exists and was not overwritten.
if echo "$OUTPUT" | grep -q "⚠️ '.ws-sync' already exists in this repository."; then
    echo "✅ Appropriate warning message found: '.ws-sync' already exists."
else
    echo "ERROR: Expected warning message not found in output." >&2
    echo "Command Output: $OUTPUT" >&2
    exit 1
fi

# Verify that the content of .ws-sync remains unchanged
CURRENT_WS_SYNC_CONTENT=$(cat .ws-sync)
if [ "$CURRENT_WS_SYNC_CONTENT" != "$EXPECTED_WS_SYNC_CONTENT" ]; then
    echo "ERROR: .ws-sync file content was unexpectedly changed." >&2
    echo "Expected content: $EXPECTED_WS_SYNC_CONTENT" >&2
    echo "Current content: $CURRENT_WS_SYNC_CONTENT" >&2
    exit 1
fi
echo "✅ .ws-sync file content remained unchanged."

# Verify that the command exited with status 0 (success)
if [ "$EXIT_CODE" -ne 0 ]; then
    echo "ERROR: Command unexpectedly exited with non-zero status." >&2
    echo "Command Output: $OUTPUT" >&2
    exit 1
fi
echo "✅ Command exited with status 0 as expected."

echo "Verification complete for Test Case 8."

# --- Teardown ---
echo "Cleaning up Test Case 8..."
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 8: PASSED ==="
