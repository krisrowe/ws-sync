# Manual Test Cases for devws CLI

## General Test Strategy

This document outlines the manual test cases for the `devws` CLI. The strategy focuses on isolating testing from production configurations and ensuring a clean state before and after each test.

**Key Principles:**

*   **Integration Test Discovery (`ws-sync-test=integration`)**: Prior to executing any specific test case, we use the `ws-sync-test=integration` label to discover the designated GCP Project and GCS Bucket for integration testing purposes. This label is purely for discovery and is *not* manipulated during test case execution. It also ensures that a dedicated environment is established for testing, separate from development or production. **Note: After applying GCS labels, it is recommended to wait at least 5-10 seconds to allow for propagation across GCP.**
*   **Test-Specific Labeling (`ws-sync-test-case`)**: For the actual execution of test cases that involve labeling resources, we will use a distinct label key: `ws-sync-test-case`. This label will be temporarily applied to the `YOUR_TEST_PROJECT_ID` and `YOUR_TEST_BUCKET_NAME` (identified during initial setup) *for the duration of the specific test case*.
*   **No Interference with Production (`ws-sync=default`)**: At no point will the `ws-sync=default` label be used or set by these manual test cases. This is crucial to prevent any accidental modification of production-configured resources. The `ws-sync` label is the default used by the CLI in a production context when environment variables are not set.
*   **Isolated Configuration**: Each test case will utilize its own temporary configuration file, ensuring no conflicts with a user's global `~/.devws/config.yaml` or previous test runs.
*   **Clean State**: Each test case includes mandatory setup (creating temporary directories, setting environment variables, applying test labels) and teardown (cleaning up directories, removing test labels, unsetting environment variables) steps to maintain a pristine environment.

### Test Execution Context

To ensure isolation and prevent corruption of the source code repository, the following conventions must be strictly followed during test execution:

*   **CLI Invocation**: All `python3 -m devws_cli.cli <command>` invocations must be executed from the project root directory (`/home/mytexoma/ws-sync`). This ensures that the CLI can correctly locate its modules and configuration files.
*   **Temporary Working Directories**: Each test case will operate within its own dedicated temporary directory (e.g., `/tmp/devws_test_1`, `/tmp/devws_test_2`, etc.). This directory will serve as the current working directory (`cwd`) for any commands that create or modify files (e.g., `rm -f .ws-sync`, `echo "..." > .ws-sync`). The `PROJ_LOCAL_CONFIG_SYNC_PATH` environment variable will be set to this temporary directory to ensure that `local` commands (push/pull/init) and the `.ws-sync` file operate within this isolated space. The `PROJ_LOCAL_CONFIG_SYNC_PATH` environment variable will be set to this temporary directory to ensure that `local` commands (push/pull/init) and the `.ws-sync` file operate within this isolated space.
*   **Environment Variable Usage**: Environment variables such as `WS_SYNC_CONFIG` and `DEVWS_WS_SYNC_LABEL_KEY` are critical for directing the `devws_cli` to use test-specific configurations and labels, ensuring that operations are confined to the temporary test environment and do not interfere with the main repository or global user configurations.

---

### Environment Variables for Test Overrides

The `devws` CLI provides environment variables to override default behaviors, facilitating isolated testing:

| Environment Variable          | Purpose                                                                                                                                              | Example Usage                                                                       |
| :---------------------------- | :----------------------------------------------------------------0----------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------- |
| `WS_SYNC_CONFIG`              | Specifies the path to the global configuration file. Overrides the default `~/.devws/config.yaml`. Used to point to a temporary config file for tests. | `export WS_SYNC_CONFIG=/tmp/devws_test_config_XXXX.yaml`                            |
| `DEVWS_WS_SYNC_LABEL_KEY`     | Overrides the default `ws-sync` label key used by the CLI for applying/checking resource labels. Set to `ws-sync-test-case` for manual testing.       | `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`                                  |
| `PROJ_LOCAL_CONFIG_SYNC_PATH` | Overrides the current working directory for `local` commands (push/pull/init) and the location of the `.ws-sync` file. | `export PROJ_LOCAL_CONFIG_SYNC_PATH=/tmp/devws_test_X` |

---

## Initial Test Setup

Before running any manual tests, you need to identify a GCP Project ID and a GCS Bucket Name that are specifically labeled for integration testing purposes. These resources will be used as the targets for all subsequent test cases.

**Steps to Identify Test Resources:**

1.  **Find the Project ID**:
    *   Run the following command to list projects labeled `ws-sync-test=integration`:
        ```bash
        gcloud projects list --filter="labels.ws-sync-test=integration" --format="value(project_id)"
        ```
    *   **Validation**:
        *   Ensure this command returns **exactly one** project ID.
        *   If it returns zero or more than one, you must resolve this manually (e.g., by labeling a project with `ws-sync-test=integration` or removing ambiguous existing labels) before proceeding.
    *   Once identified, note this Project ID. Let's refer to it as `YOUR_TEST_PROJECT_ID`.

2.  **Find the GCS Bucket Name**:
    *   Run the following command to list buckets labeled `ws-sync-test=integration` within `YOUR_TEST_PROJECT_ID`:
        ```bash
        gcloud storage buckets list --project YOUR_TEST_PROJECT_ID --filter="labels.ws-sync-test=integration" --format="value(name)"
        ```
    *   **Validation**:
        *   Ensure this command returns **exactly one** bucket name.
        *   If it returns zero or more than one, you must resolve this manually (e.g., by labeling a bucket with `ws-sync-test=integration` or removing ambiguous existing labels) before proceeding.
    *   Once identified, note this Bucket Name. Let's refer to it as `YOUR_TEST_BUCKET_NAME`.

**Important**: All subsequent test cases will assume that `YOUR_TEST_PROJECT_ID` and `YOUR_TEST_BUCKET_NAME` have been correctly identified and are unique. Replace placeholders like `YOUR_TEST_PROJECT_ID` and `YOUR_TEST_BUCKET_NAME` in the test steps with these identified values.

---

## 1. Auto-discovery of Labeled Resources
**Summary**: Run 'devws setup' with no local config file or command-line arguments, and confirm it finds the labeled project and GCS bucket, then updates the temporary config file.
**Implementation Steps**:
*   **Setup**:
    *   Create a temporary directory for this test and navigate into it: `mkdir -p /tmp/devws_test_1 && cd /tmp/devws_test_1`
    *   Set a temporary config file path: `export WS_SYNC_CONFIG=$(mktemp --tmpdir=/tmp devws_test_config_XXXX.yaml)`
    *   Set the test-specific label key: `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`
    *   Ensure the temporary config file is clean: `rm -f $WS_SYNC_CONFIG`
    *   Ensure no existing `.ws-sync` file in the current directory: `rm -f .ws-sync`
    *   Apply the `ws-sync-test-case` label to the GCP project and GCS bucket:
        *   `gcloud alpha projects update YOUR_TEST_PROJECT_ID --update-labels=ws-sync-test-case=default`
        *   `gsutil label ch -l ws-sync-test-case:default gs://YOUR_TEST_BUCKET_NAME`
*   **Execution**:
    *   Run the setup command: `python3 -m devws_cli.cli setup --component proj_local_config_sync`
*   **Verification**:
    *   Verify that the temporary config file (`$WS_SYNC_CONFIG`) is created and contains the `project_id` and `bucket_name` under the `default` profile.
        *   `cat $WS_SYNC_CONFIG`
    *   Verify that the project and bucket are labeled `ws-sync-test-case=default`.
        *   `gcloud projects describe YOUR_TEST_PROJECT_ID --format="yaml(labels)" | grep "ws-sync-test-case: default"`
        *   `gsutil label get gs://YOUR_TEST_BUCKET_NAME | grep "ws-sync-test-case: default"`
*   **Teardown**:
    *   Remove the `ws-sync-test-case` label from the GCP project and GCS bucket:
        *   `gcloud alpha projects update YOUR_TEST_PROJECT_ID --remove-labels=ws-sync-test-case`
        *   `gsutil label ch -d ws-sync-test-case gs://YOUR_TEST_BUCKET_NAME`
    *   Clean up the temporary directory: `cd - && rm -rf /tmp/devws_test_1`
    *   Unset environment variables: `unset WS_SYNC_CONFIG DEVWS_WS_SYNC_LABEL_KEY`

## 2. Explicit Project and Bucket Configuration
**Summary**: Run 'devws setup' specifying a project and bucket, and confirm it labels that project and bucket with the `ws-sync-test-case` label, then updates the temporary config file.
**Implementation Steps**:
*   **Setup**:
    *   Create a temporary directory for this test and navigate into it: `mkdir -p /tmp/devws_test_2 && cd /tmp/devws_test_2`
    *   Set a temporary config file path: `export WS_SYNC_CONFIG=$(mktemp --tmpdir=/tmp devws_test_config_XXXX.yaml)`
    *   Set the test-specific label key: `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`
    *   Ensure the temporary config file is clean: `rm -f $WS_SYNC_CONFIG`
    *   Ensure no existing `.ws-sync` file in the current directory: `rm -f .ws-sync`
    *   Ensure the GCP project and GCS bucket are *not* currently labeled `ws-sync-test-case`:
        *   `gcloud alpha projects update YOUR_TEST_PROJECT_ID --remove-labels=ws-sync-test-case`
        *   `gsutil label ch -d ws-sync-test-case gs://YOUR_TEST_BUCKET_NAME`
*   **Execution**:
    *   Run the setup command with explicit arguments: `python3 -m devws_cli.cli setup --component proj_local_config_sync --project-id YOUR_TEST_PROJECT_ID --bucket-name YOUR_TEST_BUCKET_NAME`
*   **Verification**:
    *   Verify that the temporary config file (`$WS_SYNC_CONFIG`) is created and contains `YOUR_TEST_PROJECT_ID` and `YOUR_TEST_BUCKET_NAME` under the `default` profile.
        *   `cat $WS_SYNC_CONFIG`
    *   Verify that `YOUR_TEST_PROJECT_ID` and `YOUR_TEST_BUCKET_NAME` are labeled `ws-sync-test-case=default`.
        *   `gcloud projects describe YOUR_TEST_PROJECT_ID --format="yaml(labels)" | grep "ws-sync-test-case: default"`
        *   `gsutil label get gs://YOUR_TEST_BUCKET_NAME | grep "ws-sync-test-case: default"`
*   **Teardown**:
    *   Remove the `ws-sync-test-case` label from the GCP project and GCS bucket:
        *   `gcloud alpha projects update YOUR_TEST_PROJECT_ID --remove-labels=ws-sync-test-case`
        *   `gsutil label ch -d ws-sync-test-case gs://YOUR_TEST_BUCKET_NAME`
    *   Clean up the temporary directory: `cd - && rm -rf /tmp/devws_test_2`
    *   Unset environment variables: `unset WS_SYNC_CONFIG DEVWS_WS_SYNC_LABEL_KEY`

## 3. Local Push Functionality
**Summary**: Run 'devws local push' in a temporary folder while the local config file contains a valid project and bucket name, and confirm using `gsutil` before and after that files were pushed.
**Implementation Steps**:
*   **Setup**:
    *   Create a temporary directory for this test and navigate into it: `mkdir -p /tmp/devws_test_3 && cd /tmp/devws_test_3`
    *   Set a temporary config file path: `export WS_SYNC_CONFIG=$(mktemp --tmpdir=/tmp devws_test_config_XXXX.yaml)`
    *   Set the test-specific label key: `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`
    *   Set the local config sync path: `export PROJ_LOCAL_CONFIG_SYNC_PATH=/tmp/devws_test_3`
    *   Ensure the temporary config file is clean: `rm -f $WS_SYNC_CONFIG`
    *   Ensure no existing `.ws-sync` file in the current directory: `rm -f .ws-sync`
    *   Create the temporary config file with test resources:
        ```yaml
        # Save this content to $WS_SYNC_CONFIG
        components:
          proj_local_config_sync:
            project_id: YOUR_TEST_PROJECT_ID
            bucket_name: YOUR_TEST_BUCKET_NAME
        ```
    *   Create a `.ws-sync` file with some content to push: `echo "test_file.txt" > .ws-sync`
    *   Create the file specified in `.ws-sync`: `echo "This is a test file content." > test_file.txt`
*   **Execution**:
    *   Verify the file does NOT exist in the GCS bucket: `gsutil ls gs://YOUR_TEST_BUCKET_NAME/test_file.txt` (This should return an error).
    *   Run the push command: `python3 -m devws_cli.cli local push`
*   **Verification**:
    *   Verify the file now exists in the GCS bucket and its content matches:
        *   `gsutil cat gs://YOUR_TEST_BUCKET_NAME/test_file.txt`
        *   `cat test_file.txt` (Compare outputs - should be identical)
*   **Teardown**:
    *   Clean up the temporary file in GCS: `gsutil rm gs://YOUR_TEST_BUCKET_NAME/test_file.txt`
    *   Clean up the temporary directory: `cd /home/mytexoma/ws-sync && rm -rf /tmp/devws_test_3`
    *   Unset environment variables: `unset WS_SYNC_CONFIG DEVWS_WS_SYNC_LABEL_KEY PROJ_LOCAL_CONFIG_SYNC_PATH`

## 4. Local Pull Functionality
**Summary**: Run 'devws local pull' in a temporary folder while the temporary config file contains a valid project and bucket name, and confirm using `gsutil` before and after that files were pulled.
**Implementation Steps**:
*   **Setup**:
    *   Create a temporary directory for this test and navigate into it: `mkdir -p /tmp/devws_test_4 && cd /tmp/devws_test_4`
    *   Set a temporary config file path: `export WS_SYNC_CONFIG=$(mktemp --tmpdir=/tmp devws_test_config_XXXX.yaml)`
    *   Set the test-specific label key: `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`
    *   Set the local config sync path: `export PROJ_LOCAL_CONFIG_SYNC_PATH=/tmp/devws_test_4`
    *   Create the temporary config file with test resources:
        ```yaml
        # Save this content to $WS_SYNC_CONFIG
        components:
          proj_local_config_sync:
            project_id: YOUR_TEST_PROJECT_ID
            bucket_name: YOUR_TEST_BUCKET_NAME
        ```
    *   Create a `.ws-sync` file with the name of a file to pull: `echo "pulled_file.txt" > .ws-sync`
    *   Manually upload a file to the GCS bucket: `echo "Content from GCS." | gsutil cp - gs://YOUR_TEST_BUCKET_NAME/pulled_file.txt`
*   **Execution**:
    *   Verify the file does NOT exist locally: `ls pulled_file.txt` (This should return an error).
    *   Run the pull command: `python3 -m devws_cli.cli local pull`
*   **Verification**:
    *   Verify the file now exists locally and its content matches the GCS version:
        *   `cat pulled_file.txt`
*   **Teardown**:
    *   Clean up the temporary file in GCS: `gsutil rm gs://YOUR_TEST_BUCKET_NAME/pulled_file.txt`
    *   Clean up the temporary directory: `cd /home/mytexoma/ws-sync && rm -rf /tmp/devws_test_4`
    *   Unset environment variables: `unset WS_SYNC_CONFIG DEVWS_WS_SYNC_LABEL_KEY PROJ_LOCAL_CONFIG_SYNC_PATH`

## 5. Negative Test Case: Push without .ws-sync
**Summary**: Run 'devws local push' when there is no `.ws-sync` file, expecting an error.
**Implementation Steps**:
*   **Setup**:
    *   Create a temporary directory for this test and navigate into it: `mkdir -p /tmp/devws_test_5 && cd /tmp/devws_test_5`
    *   Set a temporary config file path: `export WS_SYNC_CONFIG=$(mktemp --tmpdir=/tmp devws_test_config_XXXX.yaml)`
    *   Set the test-specific label key: `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`
    *   Set the local config sync path: `export PROJ_LOCAL_CONFIG_SYNC_PATH=/tmp/devws_test_5`
    *   Create the temporary config file with test resources:
        ```yaml
        # Save this content to $WS_SYNC_CONFIG
        components:
          proj_local_config_sync:
            project_id: YOUR_TEST_PROJECT_ID
            bucket_name: YOUR_TEST_BUCKET_NAME
        ```
    *   Ensure no `.ws-sync` file exists: `rm -f .ws-sync`
*   **Execution**:
    *   Run the push command: `python3 -m devws_cli.cli local push`
*   **Verification**:
    *   Verify that an appropriate error message is displayed (e.g., "Error: .ws-sync file not found.").
*   **Teardown**:
    *   Clean up the temporary directory: `cd /home/mytexoma/ws-sync && rm -rf /tmp/devws_test_5`
    *   Unset environment variables: `unset WS_SYNC_CONFIG DEVWS_WS_SYNC_LABEL_KEY PROJ_LOCAL_CONFIG_SYNC_PATH`

## 6. Negative Test Case: Pull without .ws-sync
**Summary**: Run 'devws local pull' where there is no `.ws-sync` file, expecting an error.
**Implementation Steps**:
*   **Setup**:
    *   Create a temporary directory for this test and navigate into it: `mkdir -p /tmp/devws_test_6 && cd /tmp/devws_test_6`
    *   Set a temporary config file path: `export WS_SYNC_CONFIG=$(mktemp --tmpdir=/tmp devws_test_config_XXXX.yaml)`
    *   Set the test-specific label key: `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`
    *   Set the local config sync path: `export PROJ_LOCAL_CONFIG_SYNC_PATH=/tmp/devws_test_6`
    *   Create the temporary config file with test resources:
        ```yaml
        # Save this content to $WS_SYNC_CONFIG
        components:
          proj_local_config_sync:
            project_id: YOUR_TEST_PROJECT_ID
            bucket_name: YOUR_TEST_BUCKET_NAME
        ```
    *   Ensure no `.ws-sync` file exists: `rm -f .ws-sync`
*   **Execution**:
    *   Run the pull command: `python3 -m devws_cli.cli local pull`
*   **Verification**:
    *   Verify that an appropriate error message is displayed (e.g., "Error: .ws-sync file not found.").
*   **Teardown**:
    *   Clean up the temporary directory: `cd /home/mytexoma/ws-sync && rm -rf /tmp/devws_test_6`
    *   Unset environment variables: `unset WS_SYNC_CONFIG DEVWS_WS_SYNC_LABEL_KEY PROJ_LOCAL_CONFIG_SYNC_PATH`

## 7. Test devws local init (no .ws-sync file)
**Summary**: Test 'devws local init' where there is no `.ws-sync` file, expecting it to be created.
**Implementation Steps**:
*   **Setup**:
    *   Create a temporary directory for this test and navigate into it: `mkdir -p /tmp/devws_test_7 && cd /tmp/devws_test_7`
    *   Set a temporary config file path: `export WS_SYNC_CONFIG=$(mktemp --tmpdir=/tmp devws_test_config_XXXX.yaml)`
    *   Set the test-specific label key: `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`
    *   Set the local config sync path: `export PROJ_LOCAL_CONFIG_SYNC_PATH=/tmp/devws_test_7`
    *   Create the temporary config file with test resources:
        ```yaml
        # Save this content to $WS_SYNC_CONFIG
        components:
          proj_local_config_sync:
            project_id: YOUR_TEST_PROJECT_ID
            bucket_name: YOUR_TEST_BUCKET_NAME
        ```
    *   Ensure no `.ws-sync` file exists: `rm -f .ws-sync`
*   **Execution**:
    *   Run the init command: `python3 -m devws_cli.cli local init`
*   **Verification**:
    *   Verify that a `.ws-sync` file is created: `ls .ws-sync`
    *   Verify that the `.ws-sync` file contains default content or a header: `cat .ws-sync`
*   **Teardown**:
    *   Clean up the temporary directory: `cd /home/mytexoma/ws-sync && rm -rf /tmp/devws_test_7`
    *   Unset environment variables: `unset WS_SYNC_CONFIG DEVWS_WS_SYNC_LABEL_KEY PROJ_LOCAL_CONFIG_SYNC_PATH`

## 8. Test devws local init (with existing .ws-sync file)
**Summary**: Test 'devws local init' where there is already a `.ws-sync` file, expecting it not to be overwritten.
**Implementation Steps**:
*   **Setup**:
    *   Create a temporary directory for this test and navigate into it: `mkdir -p /tmp/devws_test_8 && cd /tmp/devws_test_8`
    *   Set a temporary config file path: `export WS_SYNC_CONFIG=$(mktemp --tmpdir=/tmp devws_test_config_XXXX.yaml)`
    *   Set the test-specific label key: `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`
    *   Set the local config sync path: `export PROJ_LOCAL_CONFIG_SYNC_PATH=/tmp/devws_test_8`
    *   Create the temporary config file with test resources:
        ```yaml
        # Save this content to $WS_SYNC_CONFIG
        components:
          proj_local_config_sync:
            project_id: YOUR_TEST_PROJECT_ID
            bucket_name: YOUR_TEST_BUCKET_NAME
        ```
    *   Create an existing `.ws-sync` file with some content: `echo "existing_content.txt" > .ws-sync`
*   **Execution**:
    *   Run the init command: `python3 -m devws_cli.cli local init`
*   **Verification**:
    *   Verify that a message is displayed indicating that `.ws-sync` already exists and was not overwritten.
    *   Verify that the content of `.ws-sync` remains unchanged: `cat .ws-sync` (should still show "existing_content.txt")
*   **Teardown**:
    *   Clean up the temporary directory: `cd /home/mytexoma/ws-sync && rm -rf /tmp/devws_test_8`
    *   Unset environment variables: `unset WS_SYNC_CONFIG DEVWS_WS_SYNC_LABEL_KEY PROJ_LOCAL_CONFIG_SYNC_PATH`