#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Common Variables ---
PROJECT_ROOT="/home/user/ws-sync"

# --- Functions for Test Setup ---

# Function to identify the integration testing project ID
identify_project_id() {
    echo "Identifying YOUR_TEST_PROJECT_ID..."
    YOUR_TEST_PROJECT_ID=$(gcloud projects list --filter="labels.ws-sync-test=integration" --format="value(project_id)")
    if [ -z "$YOUR_TEST_PROJECT_ID" ]; then
        echo "ERROR: No project found with label 'ws-sync-test=integration'. Please label one project." >&2
        exit 1
    fi
    if [[ $(echo "$YOUR_TEST_PROJECT_ID" | wc -l) -ne 1 ]]; then
        echo "ERROR: More than one project found with label 'ws-sync-test=integration'. Please ensure only one is labeled." >&2
        exit 1
    fi
    echo "Identified YOUR_TEST_PROJECT_ID: $YOUR_TEST_PROJECT_ID"
    export YOUR_TEST_PROJECT_ID
}

# Function to identify the integration testing bucket name
identify_bucket_name() {
    echo "Identifying YOUR_TEST_BUCKET_NAME..."
    YOUR_TEST_BUCKET_NAME=$(gcloud storage buckets list --project "$YOUR_TEST_PROJECT_ID" --filter="labels.ws-sync-test=integration" --format="value(name)")
    if [ -z "$YOUR_TEST_BUCKET_NAME" ]; then
        echo "ERROR: No bucket found with label 'ws-sync-test=integration' in project '$YOUR_TEST_PROJECT_ID'. Please label one bucket." >&2
        exit 1
    fi
    if [[ $(echo "$YOUR_TEST_BUCKET_NAME" | wc -l) -ne 1 ]]; then
        echo "ERROR: More than one bucket found with label 'ws-sync-test=integration' in project '$YOUR_TEST_PROJECT_ID'. Please ensure only one is labeled." >&2
        exit 1
    fi
    echo "Identified YOUR_TEST_BUCKET_NAME: $YOUR_TEST_BUCKET_NAME"
    export YOUR_TEST_BUCKET_NAME
}

# Function to set common environment variables for a test case
set_common_test_env() {
    local TEST_DIR="$1"
    export WS_SYNC_CONFIG=$(mktemp --tmpdir="$TEST_DIR" devws_test_config_XXXX.yaml)
    export DEVWS_WS_SYNC_LABEL_KEY="ws-sync-test-case"
    export PROJ_LOCAL_CONFIG_SYNC_PATH="$TEST_DIR" # For local commands
    echo "Common environment variables set:"
    echo "  WS_SYNC_CONFIG=$WS_SYNC_CONFIG"
    echo "  DEVWS_WS_SYNC_LABEL_KEY=$DEVWS_WS_SYNC_LABEL_KEY"
    echo "  PROJ_LOCAL_CONFIG_SYNC_PATH=$PROJ_LOCAL_CONFIG_SYNC_PATH"
}

# Function to unset common environment variables
unset_common_test_env() {
    unset WS_SYNC_CONFIG
    unset DEVWS_WS_SYNC_LABEL_KEY
    unset PROJ_LOCAL_CONFIG_SYNC_PATH
    echo "Common environment variables unset."
}

# Function to clean up a test directory
cleanup_test_dir() {
    local TEST_DIR="$1"
    echo "Cleaning up test directory: $TEST_DIR"
    rm -rf "$TEST_DIR"
}

# Function to apply GCS labels (used in setup)
apply_gcs_labels() {
    local PROJECT_ID="$1"
    local BUCKET_NAME="$2"
    echo "Applying ws-sync-test-case=default label to project $PROJECT_ID..."
    gcloud alpha projects update "$PROJECT_ID" --update-labels=ws-sync-test-case=default
    echo "Applying ws-sync-test-case:default label to bucket gs://$BUCKET_NAME..."
    gsutil label ch -l ws-sync-test-case:default "gs://$BUCKET_NAME"
}

# Function to remove GCS labels (used in teardown)
remove_gcs_labels() {
    local PROJECT_ID="$1"
    local BUCKET_NAME="$2"
    echo "Removing ws-sync-test-case label from project $PROJECT_ID..."
    gcloud alpha projects update "$PROJECT_ID" --remove-labels=ws-sync-test-case || true # Ignore errors if label doesn't exist
    echo "Removing ws-sync-test-case label from bucket gs://$BUCKET_NAME..."
    gsutil label ch -d ws-sync-test-case "gs://$BUCKET_NAME" || true # Ignore errors if label doesn't exist
}

# Function to setup the base test environment including a dummy git repo and basic devws config
setup_test_environment() {
    local TEST_DIR="$1"
    local REPO_DIR="$2"

    echo "Setting up test directory: $TEST_DIR"
    rm -rf "$TEST_DIR" # Ensure clean slate
    mkdir -p "$REPO_DIR"
    cd "$REPO_DIR"

    set_common_test_env "$REPO_DIR" # Sets WS_SYNC_CONFIG, DEVWS_WS_SYNC_LABEL_KEY, PROJ_LOCAL_CONFIG_SYNC_PATH

    # Ensure the temporary config file is clean
    rm -f "$WS_SYNC_CONFIG"
    # Ensure no existing .ws-sync file in the current directory
    rm -f ".ws-sync"

    # Create a dummy Git repository
    git init > /dev/null
    git config user.email "test@example.com"
    git config user.name "Test User"
    touch initial.txt
    git add .
    git commit -m "Initial commit" > /dev/null
    git remote add origin https://github.com/test_user/test_repo.git > /dev/null 2>&1 # Add dummy remote
}

# Function to configure the GCS test profile by directly writing to WS_SYNC_CONFIG
configure_gcs_test_config() {
    local PROJECT_ID="$1"
    local BUCKET_NAME="$2"
    local WS_SYNC_CONFIG="$3"

    echo "Pre-configuring test GCS profile in config file: $WS_SYNC_CONFIG"
    cat <<EOF > "$WS_SYNC_CONFIG"
gcs_profiles:
  default:
    project_id: "$PROJECT_ID"
    bucket_name: "$BUCKET_NAME"
EOF
}

# Function to get the GCS path prefix for the test repository
get_test_gcs_path_prefix() {
    local BUCKET_NAME="$1"
    local OWNER="test_user" # Hardcoded to match dummy git remote
    local REPO_NAME="test_repo" # Hardcoded to match dummy git remote
    echo "gs://$BUCKET_NAME/projects/$OWNER/$REPO_NAME"
}

# Function to run a command in the test directory
run_in_test_dir() {
    local TEST_DIR="$1"
    shift
    (cd "$TEST_DIR" && "$@")
}