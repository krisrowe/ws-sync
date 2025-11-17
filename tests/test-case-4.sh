#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 4: Local Pull Functionality ==="

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

# Pre-configure the global config file with test resources
echo "Pre-configuring global config file: $WS_SYNC_CONFIG"
cat <<EOF > "$WS_SYNC_CONFIG"
gcs_profiles:
  default:
    project_id: "$YOUR_TEST_PROJECT_ID"
    bucket_name: "$YOUR_TEST_BUCKET_NAME"
EOF

# Create a dummy .gitignore file
echo "Creating .gitignore file..."
cat <<EOF > .gitignore
.env
# Other ignored files
EOF

# Create a .ws-sync file with the name of a file to pull
echo "Creating .ws-sync file..."
echo ".env" > .ws-sync

# Manually upload a file to the GCS bucket
echo "Manually uploading .env to GCS..."
echo "Content from GCS." | gsutil cp - "gs://$YOUR_TEST_BUCKET_NAME/projects/github-user/ws-sync/.env"

echo "Setup complete for Test Case 4."

# --- Execution ---
echo "Verifying .env does NOT exist locally..."
if [ -f ".env" ]; then
    rm .env
fi

echo "Executing devws cli local pull command..."
(cd "$PROJECT_ROOT" && python3 -m devws_cli.cli local pull)

echo "Execution complete for Test Case 4."

# --- Verification ---
echo "Verifying results for Test Case 4..."

# Verify the file now exists locally and its content matches the GCS version
LOCAL_CONTENT=$(cat .env)
EXPECTED_CONTENT="Content from GCS."

if [ "$LOCAL_CONTENT" != "$EXPECTED_CONTENT" ]; then
    echo "ERROR: Content of .env locally does not match GCS content." >&2
    echo "Local Content: $LOCAL_CONTENT" >&2
    echo "Expected Content: $EXPECTED_CONTENT" >&2
    exit 1
fi
echo "✅ Content of .env locally matches GCS content."

echo "Verification complete for Test Case 4."

# --- Teardown ---
echo "Cleaning up Test Case 4..."
gsutil rm "gs://$YOUR_TEST_BUCKET_NAME/projects/github-user/ws-sync/.env"
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 4: PASSED ==="
