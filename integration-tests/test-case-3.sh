#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 3: Local Push Functionality ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_3"
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

# Ensure no labels are present on the project and bucket from previous runs
remove_gcs_labels "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME"

# Pre-configure the global config file with test resources
echo "Pre-configuring global config file: $WS_SYNC_CONFIG"
cat <<EOF > "$WS_SYNC_CONFIG_FILE"
gcs_profiles:
  default:
    project_id: "$YOUR_TEST_PROJECT_ID"
    bucket_name: "$YOUR_TEST_BUCKET_NAME"
EOF

# Create a .ws-sync file with some content to push
echo "Creating .ws-sync file..."
echo ".env" > .ws-sync # Manage .env file

# Create a dummy .gitignore file
echo "Creating .gitignore file..."
cat <<EOF > .gitignore
.env
# Other ignored files
EOF

# Create the file specified in .ws-sync
echo "Creating .env file..."
echo "DUMMY_API_KEY=12345" > .env

echo "Setup complete for Test Case 3."

# --- Execution ---
echo "Verifying test_file.txt does NOT exist in GCS bucket..."
if gsutil ls "gs://$YOUR_TEST_BUCKET_NAME/test_file.txt" 2>/dev/null; then
    echo "WARNING: test_file.txt already exists in GCS. Removing it."
    gsutil rm "gs://$YOUR_TEST_BUCKET_NAME/test_file.txt"
fi

echo "Executing devws cli local push command..."
(cd "$PROJECT_ROOT" && python3 -m devws_cli.cli local push)

echo "Execution complete for Test Case 3."

# --- Verification ---
echo "Verifying results for Test Case 3..."

# Verify the file now exists in the GCS bucket and its content matches
GCS_CONTENT=$(gsutil cat "gs://$YOUR_TEST_BUCKET_NAME/projects/github-user/ws-sync/.env")
LOCAL_CONTENT=$(cat .env)

if [ "$GCS_CONTENT" != "$LOCAL_CONTENT" ]; then
    echo "ERROR: Content of .env in GCS does not match local content." >&2
    echo "GCS Content: $GCS_CONTENT" >&2
    echo "Local Content: $LOCAL_CONTENT" >&2
    exit 1
fi
echo "✅ Content of .env in GCS matches local content."

echo "Verification complete for Test Case 3."

# --- Teardown ---
echo "Cleaning up Test Case 3..."
gsutil rm "gs://$YOUR_TEST_BUCKET_NAME/projects/github-user/ws-sync/.env"
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 3: PASSED ==="
