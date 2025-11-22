#!/bin/bash

# Source common test functions
source "$(dirname "$0")/test-common.sh"

echo "=== Running Test Case 4: Local Pull Functionality ==="

# --- Setup ---
TEST_DIR="/tmp/devws_test_4"
REPO_DIR="$TEST_DIR/test_repo"

setup_test_environment "$TEST_DIR" "$REPO_DIR"

# Identify project and bucket
identify_project_id
identify_bucket_name

# Configure GCS test profile by directly writing to WS_SYNC_CONFIG
configure_gcs_test_config "$YOUR_TEST_PROJECT_ID" "$YOUR_TEST_BUCKET_NAME" "$WS_SYNC_CONFIG"

# Construct GCS_REPO_PATH using the new common function
GCS_REPO_PATH=$(get_test_gcs_path_prefix "$YOUR_TEST_BUCKET_NAME")

# Create a dummy .gitignore file
echo "Creating .gitignore file..."
cat <<EOF > .gitignore
.env
# Other ignored files
EOF

# Create a .ws-sync file with the name of a file and a folder to pull
echo "Creating .ws-sync file..."
cat <<EOF > .ws-sync
.env
my_restored_folder/
EOF

# Manually upload a file to the GCS bucket
echo "Manually uploading .env to GCS..."
echo "Content from GCS." | gsutil cp - "$GCS_REPO_PATH/.env"

# Manually upload a file inside a folder to GCS
echo "Manually uploading my_restored_folder/restored_file.txt to GCS..."
mkdir -p my_restored_folder # Ensure local folder exists for push
echo "Folder content from GCS." | gsutil cp - "$GCS_REPO_PATH/my_restored_folder/restored_file.txt"

echo "Setup complete for Test Case 4."

# --- Execution ---
echo "Verifying .env does NOT exist locally..."
if [ -f ".env" ]; then
    rm .env
fi
echo "Verifying my_restored_folder does NOT exist locally..."
if [ -d "my_restored_folder" ]; then
    rm -rf my_restored_folder
fi

echo "Executing devws cli local pull command..."
PYTHONPATH="$PROJECT_ROOT" python3 -m devws_cli.cli local pull

echo "Execution complete for Test Case 4."

# --- Verification ---
echo "Verifying results for Test Case 4..."

# Verify the .env file
LOCAL_CONTENT_ENV=$(cat .env)
EXPECTED_CONTENT_ENV="Content from GCS."

if [ "$LOCAL_CONTENT_ENV" != "$EXPECTED_CONTENT_ENV" ]; then
    echo "ERROR: Content of .env locally does not match GCS content." >&2
    echo "Local Content: $LOCAL_CONTENT_ENV" >&2
    echo "Expected Content: $EXPECTED_CONTENT_ENV" >&2
    exit 1
fi
echo "✅ Content of .env locally matches GCS content."

# Verify the restored folder and its file
if [ ! -d "my_restored_folder" ]; then
    echo "ERROR: Directory 'my_restored_folder' was not restored." >&2
    exit 1
fi
echo "✅ Directory 'my_restored_folder' was restored."

LOCAL_CONTENT_FOLDER=$(cat my_restored_folder/restored_file.txt)
EXPECTED_CONTENT_FOLDER="Folder content from GCS."

if [ "$LOCAL_CONTENT_FOLDER" != "$EXPECTED_CONTENT_FOLDER" ]; then
    echo "ERROR: Content of my_restored_folder/restored_file.txt locally does not match GCS content." >&2
    echo "Local Content: $LOCAL_CONTENT_FOLDER" >&2
    echo "Expected Content: $EXPECTED_CONTENT_FOLDER" >&2
    exit 1
fi
echo "✅ Content of my_restored_folder/restored_file.txt locally matches GCS content."

echo "Verification complete for Test Case 4."

# --- Teardown ---
echo "Cleaning up Test Case 4..."
gsutil rm "$GCS_REPO_PATH/.env" > /dev/null 2>&1 || true
gsutil -m rm -r "$GCS_REPO_PATH/my_restored_folder/" > /dev/null 2>&1 || true
cleanup_test_dir "$TEST_DIR"
unset_common_test_env

echo "=== Test Case 4: PASSED ==="
