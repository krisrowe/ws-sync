#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 5: Negative Test Case: Push without .ws-sync ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_5"
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

# Pre-configure the global config file with test resources
echo "Pre-configuring global config file: $WS_SYNC_CONFIG"
cat <<EOF > "$WS_SYNC_CONFIG_FILE"
gcs_profiles:
  default:
    project_id: "$YOUR_TEST_PROJECT_ID"
    bucket_name: "$YOUR_TEST_BUCKET_NAME"
EOF

# Ensure no .ws-sync file exists
rm -f ".ws-sync"

echo "Setup complete for Test Case 5."

# --- Execution ---
echo "Executing devws cli local push command without .ws-sync file..."
set +e # Temporarily disable exit on error
OUTPUT=$( (cd "$PROJECT_ROOT" && python3 -m devws_cli.cli local push) 2>&1 )
EXIT_CODE=$?
set -e # Re-enable exit on error

echo "Execution complete for Test Case 5."

# --- Verification ---
echo "Verifying results for Test Case 5..."

# Verify that an appropriate error message is displayed
if echo "$OUTPUT" | grep -q "❌ '.ws-sync' not found in the current directory"; then
    echo "✅ Appropriate error message found: '.ws-sync' not found."
else
    echo "ERROR: Expected error message not found in output." >&2
    echo "Command Output: $OUTPUT" >&2
    exit 1
fi

# Verify that the command exited with a non-zero status
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "ERROR: Command unexpectedly exited with status 0 (success)." >&2
    echo "Command Output: $OUTPUT" >&2
    exit 1
fi
echo "✅ Command exited with non-zero status as expected."

echo "Verification complete for Test Case 5."

# --- Teardown ---
echo "Cleaning up Test Case 5..."
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 5: PASSED ==="
