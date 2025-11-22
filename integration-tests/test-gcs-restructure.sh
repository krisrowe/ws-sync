#!/bin/bash

# Source common test utilities
source "$(dirname "$0")/test-common.sh"

# Test setup
setup_test_environment

echo "--- Test GCS Restructure and Migration ---"

# Assuming a GCS bucket is configured and gcloud is authenticated
# Set your test bucket name here or ensure it's configured in ~/.config/devws/config.yaml
# For automated testing, this might be dynamically created/deleted or pre-configured.
TEST_GCS_BUCKET="your-test-devws-bucket" # REPLACE WITH AN ACTUAL TEST BUCKET NAME

# --- Scenario 1: Test devws local init with new GCSManager pathing ---
echo "Scenario 1: Testing devws local init"
init_git_repo "test-repo-init"
cd "test-repo-init"

# Create a dummy .gitignore and a candidate file
echo "test_file.env" > ".gitignore"
echo "LOCAL_VAR=value" > "test_file.env"

run_devws_command "local init" || fail "devws local init failed"
expect_file_content ".ws-sync" "test_file.env" || fail ".ws-sync did not contain test_file.env"

cd "$TEST_DIR"
echo "Scenario 1 PASSED"

# --- Scenario 2: Test devws local push with new GCSManager pathing ---
echo "Scenario 2: Testing devws local push"
init_git_repo "test-repo-push"
cd "test-repo-push"
echo "LOCAL_PUSH_VAR=pushed" > "push_file.env"
echo "push_file.env" > ".ws-sync"
echo "push_file.env" >> ".gitignore"

run_devws_command "local push --debug" || fail "devws local push failed"
# Verify file in GCS under the new /repos/ path
REPO_OWNER=$(get_git_repo_owner)
REPO_NAME=$(get_git_repo_name)
EXPECTED_GCS_PATH="gs://${TEST_GCS_BUCKET}/repos/${REPO_OWNER}/${REPO_NAME}/push_file.env"
gsutil ls "${EXPECTED_GCS_PATH}" > /dev/null || fail "File not found in new GCS path: ${EXPECTED_GCS_PATH}"

cd "$TEST_DIR"
echo "Scenario 2 PASSED"

# --- Scenario 3: Test devws local pull with new GCSManager pathing ---
echo "Scenario 3: Testing devws local pull"
init_git_repo "test-repo-pull"
cd "test-repo-pull"
# Assuming push_file.env is already in GCS from Scenario 2
echo "push_file.env" > ".ws-sync"
echo "push_file.env" >> ".gitignore"

rm "push_file.env" # Remove local file to test pull

run_devws_command "local pull --debug" || fail "devws local pull failed"
expect_file_content "push_file.env" "LOCAL_PUSH_VAR=pushed" || fail "File not pulled correctly"

cd "$TEST_DIR"
echo "Scenario 3 PASSED"

# --- Scenario 4: Test devws user-config backup for devws-config.yaml ---
echo "Scenario 4: Testing devws user-config backup"
# Ensure default config exists locally
rm -f "$HOME/.config/devws/config.yaml"
# Simulate running setup first to ensure default config.yaml is present.
# This assumes that devws setup will eventually create the default global config
# For now, let's just create a dummy one
mkdir -p "$HOME/.config/devws"
echo "gcs_profiles: {default: {project_id: 'test-project', bucket_name: '${TEST_GCS_BUCKET}'}}" > "$HOME/.config/devws/config.yaml"
echo "some_setting: true" >> "$HOME/.config/devws/config.yaml"

run_devws_command "user-config backup --debug" || fail "devws user-config backup failed"
EXPECTED_GCS_USER_CONFIG_PATH="gs://${TEST_GCS_BUCKET}/user-home/devws-config.yaml"
gsutil ls "${EXPECTED_GCS_USER_CONFIG_PATH}" > /dev/null || fail "devws-config.yaml not found in GCS user-home path: ${EXPECTED_GCS_USER_CONFIG_PATH}"

echo "Scenario 4 PASSED"

# --- Scenario 5: Test devws user-config restore for devws-config.yaml ---
echo "Scenario 5: Testing devws user-config restore"
rm "$HOME/.config/devws/config.yaml" # Remove local config to restore

run_devws_command "user-config restore --debug" || fail "devws user-config restore failed"
expect_file_content "$HOME/.config/devws/config.yaml" "some_setting: true" || fail "devws-config.yaml not restored correctly"

echo "Scenario 5 PASSED"

# --- Cleanup ---
echo "--- Cleaning up GCS test data ---"
cleanup_gcs_test_data "${TEST_GCS_BUCKET}" "${REPO_OWNER}" "${REPO_NAME}" "old_owner" "old_repo"
echo "GCS Cleanup Complete."

final_cleanup
echo "All tests PASSED!"
