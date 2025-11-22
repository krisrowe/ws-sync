#!/bin/bash

# Source common test functions
source "$(dirname "$0")/tests/test-common.sh"

echo "=== Cleaning up debug environment ==="

TEST_DIR="/tmp/devws_test_debug"
REPO_DIR="$TEST_DIR/test_repo"

# Identify project and bucket (if needed for gsutil rm)
identify_project_id
identify_bucket_name

# Construct GCS_REPO_PATH using the new common function
GCS_REPO_PATH=$(get_test_gcs_path_prefix "$YOUR_TEST_BUCKET_NAME")

gsutil -m rm -r "$GCS_REPO_PATH" > /dev/null 2>&1 || true # Clean up all GCS objects under the repo path

cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "Cleanup complete for debug environment."