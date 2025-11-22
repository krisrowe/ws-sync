#!/bin/bash

# Source common test functions
source "$(dirname "$0")/tests/test-common.sh"

echo "=== Setting up debug environment ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_debug"
REPO_DIR="$TEST_DIR/test_repo" # Use a nested directory for git repo

setup_test_environment "$TEST_DIR" "$REPO_DIR"

# Identify project and bucket
identify_project_id
identify_bucket_name

# Configure GCS test profile by directly writing to WS_SYNC_CONFIG
configure_gcs_test_config "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME" "$WS_SYNC_CONFIG"

# Construct GCS_REPO_PATH using the new common function
GCS_REPO_PATH=$(get_test_gcs_path_prefix "$YOUR_TEST_BUCKET_NAME")

# Change to REPO_DIR as the debug script will run from here
cd "$REPO_DIR" || exit 1

# --- Create files and GCS objects for dry-run scenarios ---


# 1. file_exists_local_and_gcs_same.txt
echo "local_same_content" > file_exists_local_and_gcs_same.txt
gsutil cp file_exists_local_and_gcs_same.txt "$GCS_REPO_PATH/file_exists_local_and_gcs_same.txt" > /dev/null 2>&1

# 2. file_exists_local_and_gcs_diff.txt
echo "local_diff_content" > file_exists_local_and_gcs_diff.txt
echo "gcs_diff_content" > gcs_version_diff.txt
gsutil cp gcs_version_diff.txt "$GCS_REPO_PATH/file_exists_gcs_only.txt" > /dev/null 2>&1 # This is intentional for the test
rm gcs_version_diff.txt

# 3. file_exists_local_only.txt
echo "local_only_content" > file_exists_local_only.txt

# 4. file_exists_gcs_only.txt
echo "gcs_only_content" > gcs_file.txt
gsutil cp gcs_file.txt "$GCS_REPO_PATH/file_exists_gcs_only.txt" > /dev/null 2>&1
rm gcs_file.txt

# 5. dir_exists_local_and_gcs/
mkdir dir_exists_local_and_gcs
echo "dir_file_content" > dir_exists_local_and_gcs/nested_file.txt
gsutil cp dir_exists_local_and_gcs/nested_file.txt "$GCS_REPO_PATH/dir_exists_local_and_gcs/nested_file.txt" > /dev/null 2>&1

# 6. file_ignored_by_gitignore.log
echo "ignored_content" > file_ignored_by_gitignore.log


# Create .ws-sync file with all patterns
WS_SYNC_CONTENT="\
file_exists_local_and_gcs_same.txt
file_exists_local_and_gcs_diff.txt
file_exists_local_only.txt
file_exists_gcs_only.txt
dir_exists_local_and_gcs/
file_ignored_by_gitignore.log"
echo "$WS_SYNC_CONTENT" > .ws-sync

# Create .gitignore file
GITIGNORE_CONTENT="\
file_ignored_by_gitignore.log"
echo "$GITIGNORE_CONTENT" > .gitignore


echo "Setup complete for debug environment."
