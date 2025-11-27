#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 9: devws local push with a directory ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_9"
echo "Setting up test directory: $TEST_DIR"
rm -rf "$TEST_DIR" # Ensure clean slate
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
sleep 5 # Wait for labels to propagate

# Create a dummy Git repository
git init > /dev/null
git config user.email "test@example.com"
git config user.name "Test User"
touch initial.txt
git add .
git commit -m "Initial commit" > /dev/null

# Create a directory and a file inside it
mkdir my_test_folder
echo "This is a test file." > my_test_folder/test_file.txt
echo "Another line." >> my_test_folder/test_file.txt

# Create .ws-sync with the directory
echo "my_test_folder/" > .ws-sync

# Create a .gitignore to ignore the folder
echo "my_test_folder/" > .gitignore

echo "Setup complete for Test Case 9."

# --- Execution ---
echo "Ensuring clean state for devws cli setup by removing labels first..."
remove_gcs_labels "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME"
sleep 5 # Wait for labels to un-propagate

echo "Executing devws cli setup command to configure GCS profile..."
(cd "$PROJECT_ROOT" && python3 -m devws_cli.cli local setup --project-id "$YOUR_TEST_PROJECT_ID" --bucket-name "$YOUR_TEST_BUCKET_NAME")

echo "Executing devws local push..."
(cd "$PROJECT_ROOT" && echo "y" | python3 -m devws_cli.cli local push)

echo "Execution complete for Test Case 9."

# --- Verification ---
echo "Verifying results for Test Case 9..."
sleep 3 # Allow GCS to become consistent

# Construct the expected GCS path for the file
OWNER=$(cd "$PROJECT_ROOT" && git config --get remote.origin.url | sed -n 's/.*github.com[\/:]\([^/]*\)\/.*/\1/p')
REPO_NAME=$(cd "$PROJECT_ROOT" && git config --get remote.origin.url | sed -n 's/.*github.com[\/:][^/]*\/\(.*\)\.git/\1/p')

EXPECTED_GCS_FILE_PATH="gs://$YOUR_TEST_BUCKET_NAME/projects/$OWNER/$REPO_NAME/my_test_folder/test_file.txt"
EXPECTED_GCS_WS_SYNC_PATH="gs://$YOUR_TEST_BUCKET_NAME/projects/$OWNER/$REPO_NAME/.ws-sync"

echo "Checking if '$EXPECTED_GCS_FILE_PATH' exists in GCS..."
if ! gsutil ls "$EXPECTED_GCS_FILE_PATH" > /dev/null 2>&1; then
    echo "ERROR: File '$EXPECTED_GCS_FILE_PATH' not found in GCS." >&2
    exit 1
fi
echo "✅ File '$EXPECTED_GCS_FILE_PATH' found in GCS."

echo "Verification complete for Test Case 9."

# --- Teardown ---
echo "Cleaning up Test Case 9..."
# Remove the uploaded directory and .ws-sync from GCS
gsutil -m rm -r "gs://$YOUR_TEST_BUCKET_NAME/projects/$OWNER/$REPO_NAME/my_test_folder/" > /dev/null 2>&1 || true
gsutil rm "$EXPECTED_GCS_WS_SYNC_PATH" > /dev/null 2>&1 || true

remove_gcs_labels "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME"
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 9: PASSED ==="