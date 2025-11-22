#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 10: devws local pull --dry-run ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_10"
REPO_DIR="$TEST_DIR/test_repo" # Use a nested directory for git repo

setup_test_environment "$TEST_DIR" "$REPO_DIR"

# Identify project and bucket
identify_project_id
identify_bucket_name

# Configure GCS test profile by directly writing to WS_SYNC_CONFIG
configure_gcs_test_config "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME" "$WS_SYNC_CONFIG"

# Construct GCS_REPO_PATH using the new common function
GCS_REPO_PATH=$(get_test_gcs_path_prefix "$YOUR_TEST_BUCKET_NAME")


# --- Create files and GCS objects for dry-run scenarios ---


# 1. file_exists_local_and_gcs_same.txt
echo "local_same_content" > file_exists_local_and_gcs_same.txt
gsutil cp file_exists_local_and_gcs_same.txt "$GCS_REPO_PATH/file_exists_local_and_gcs_same.txt" > /dev/null 2>&1

# 2. file_exists_local_and_gcs_diff.txt
echo "local_diff_content" > file_exists_local_and_gcs_diff.txt
echo "gcs_diff_content" > gcs_version_diff.txt
gsutil cp gcs_version_diff.txt "$GCS_REPO_PATH/file_exists_local_and_gcs_diff.txt" > /dev/null 2>&1
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


echo "Setup complete for Test Case 10."

# --- Execution ---

echo "Executing devws local pull --dry-run (ASCII output)..."
ASCII_OUTPUT=$(PYTHONPATH="$PROJECT_ROOT" python3 -m devws_cli.cli local pull --dry-run)
echo "$ASCII_OUTPUT"

echo "Executing devws local pull --dry-run --json (JSON output)..."
JSON_OUTPUT=$(PYTHONPATH="$PROJECT_ROOT" python3 -m devws_cli.cli local pull --dry-run --json 2>/dev/null)
echo "$JSON_OUTPUT"

echo "Execution complete for Test Case 10."

# --- Verification ---
echo "Verifying results for Test Case 10..."

# Verify ASCII output
echo "Verifying ASCII output..."
if ! echo "$ASCII_OUTPUT" | grep -q "file_exists_local_and_gcs_same.txt.*Present.*Present.*No.*Skip (Local Exists)"; then
    echo "ERROR: ASCII output missing or incorrect for file_exists_local_and_gcs_same.txt" >&2
    exit 1
fi
if ! echo "$ASCII_OUTPUT" | grep -q "file_exists_local_and_gcs_diff.txt.*Present (Different).*Present.*No.*Skip (Local Exists)"; then
    echo "ERROR: ASCII output missing or incorrect for file_exists_local_and_gcs_diff.txt" >&2
    exit 1
fi
if ! echo "$ASCII_OUTPUT" | grep -q "file_exists_local_only.txt.*Present.*Not Present.*No.*No GCS counterpart"; then
    echo "ERROR: ASCII output missing or incorrect for file_exists_local_only.txt" >&2
    exit 1
fi
if ! echo "$ASCII_OUTPUT" | grep -q "file_exists_gcs_only.txt.*Not Present.*Present.*No.*Pull"; then
    echo "ERROR: ASCII output missing or incorrect for file_exists_gcs_only.txt" >&2
    exit 1
fi
if ! echo "$ASCII_OUTPUT" | grep -q "dir_exists_local_and_gcs/.*Present (Dir).*Present.*No.*Sync Directory"; then
    echo "ERROR: ASCII output missing or incorrect for dir_exists_local_and_gcs/" >&2
    exit 1
fi
if ! echo "$ASCII_OUTPUT" | grep -q "file_ignored_by_gitignore.log.*Present.*Not Present.*Yes.*Skip (Ignored)"; then
    echo "ERROR: ASCII output missing or incorrect for file_ignored_by_gitignore.log" >&2
    exit 1
fi
echo "✅ ASCII output verification passed."

# Verify JSON output
echo "Verifying JSON output..."
python3 -c "
import json
import sys

json_data = json.loads(sys.stdin.read())

expected_results = {
    'file_exists_local_and_gcs_same.txt': {'local_status': 'Present', 'gcs_status': 'Present', 'ignored_by_gitignore': 'No', 'action': 'Skip (Local Exists)'},
    'file_exists_local_and_gcs_diff.txt': {'local_status': 'Present (Different)', 'gcs_status': 'Present', 'ignored_by_gitignore': 'No', 'action': 'Skip (Local Exists)'},
    'file_exists_local_only.txt': {'local_status': 'Present', 'gcs_status': 'Not Present', 'ignored_by_gitignore': 'No', 'action': 'No GCS counterpart'},
    'file_exists_gcs_only.txt': {'local_status': 'Not Present', 'gcs_status': 'Present', 'ignored_by_gitignore': 'No', 'action': 'Pull'},
    'dir_exists_local_and_gcs/': {'local_status': 'Present (Dir)', 'gcs_status': 'Present', 'ignored_by_gitignore': 'No', 'action': 'Sync Directory'},
    'file_ignored_by_gitignore.log': {'local_status': 'Present', 'gcs_status': 'Not Present', 'ignored_by_gitignore': 'Yes', 'action': 'Skip (Ignored)'}
}

for item in json_data:
    file_pattern = item['file_pattern']
    if file_pattern not in expected_results:
        print(f'ERROR: Unexpected file pattern in JSON: {file_pattern}', file=sys.stderr)
        sys.exit(1)
    
    for key, expected_value in expected_results[file_pattern].items():
        if item[key] != expected_value:
            print(f'ERROR: Mismatch for {file_pattern} - {key}. Expected: {expected_value}, Got: {item[key]}', file=sys.stderr)
            sys.exit(1)
print('JSON output verification passed.')
" <<< "$JSON_OUTPUT"

if [ $? -ne 0 ]; then
    echo "ERROR: JSON output verification failed." >&2
    exit 1
fi

# Verify no actual files were pulled/modified locally
echo "Verifying no local files were modified..."
if ! grep -q "local_same_content" file_exists_local_and_gcs_same.txt; then
    echo "ERROR: file_exists_local_and_gcs_same.txt content changed unexpectedly." >&2
    exit 1
fi
if ! grep -q "local_diff_content" file_exists_local_and_gcs_diff.txt; then
    echo "ERROR: file_exists_local_and_gcs_diff.txt content changed unexpectedly." >&2
    exit 1
fi
if [ -f file_exists_gcs_only.txt ]; then
    echo "ERROR: file_exists_gcs_only.txt was unexpectedly pulled." >&2
    exit 1
fi
echo "✅ No local files were modified during dry-run."


echo "Verification complete for Test Case 10."

# --- Teardown ---
echo "Cleaning up Test Case 10..."
gsutil -m rm -r "$GCS_REPO_PATH" > /dev/null 2>&1 || true # Clean up all GCS objects under the repo path

cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 10: PASSED ==="