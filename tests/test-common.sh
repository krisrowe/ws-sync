#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Common Variables ---
PROJECT_ROOT="/home/mytexoma/ws-sync"

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

# Function to run a command in the test directory
run_in_test_dir() {
    local TEST_DIR="$1"
    shift
    (cd "$TEST_DIR" && "$@")
}