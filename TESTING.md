# devws CLI Testing Strategy

This document outlines the testing strategy for the `devws` CLI, encompassing both automated unit/mock testing and integration testing.

## General Test Principles

*   **Isolation**: Tests should run in isolated environments to prevent interference with development or production configurations.
*   **Reproducibility**: Tests should yield consistent results regardless of when or where they are run.
*   **Efficiency**: Unit tests should be fast, while integration tests can involve external dependencies but should still be optimized.
*   **Clarity**: Test cases and their expected outcomes should be clear and understandable.

## Testing Approaches

### 1. Integration Tests (Shell Scripts)

Existing `.sh` files in the `integration-tests/` directory (e.g., `test-case-*.sh`, `test-gcs-restructure.sh`) serve as **integration tests**. They are designed to:

*   **Simulate End-to-End Workflows**: Verify the CLI's behavior across various commands and their interactions.
*   **Interact with Real External Dependencies**: This includes running actual `git`, `gcloud`, `gsutil` commands, and potentially a live GCS bucket (configured through test-specific labels).
*   **Environment Isolation**: Each script sets up its own temporary working directory (`PROJ_LOCAL_CONFIG_SYNC_PATH`) and temporary global config file (`WS_SYNC_CONFIG`) to ensure isolation from the user's actual environment.
*   **Idempotency and Cleanup**: Scripts typically include setup and teardown phases to leave the system in a clean state, often using shared functions from `integration-tests/test-common.sh`.

**Running Integration Tests:**

To run these tests, navigate to the project root and execute the desired script:

```bash
cd /path/to/ws-sync
./integration-tests/test-gcs-restructure.sh
# Or for all:
# for test_script in integration-tests/test-case-*.sh; do ./$test_script; done
```

**Prerequisites for Integration Tests:**

*   A configured GCP project and GCS bucket labeled with `ws-sync-test=integration`. (See `integration-tests/test-common.sh` for details on identifying these resources).
*   `gcloud` CLI installed and authenticated.
*   `gsutil` (part of `gcloud CLI`) available.
*   Python environment with `devws` installed (preferably in editable mode for local development).

### 2. Unit and Mock Tests (Pytest)

To achieve faster feedback cycles and test internal logic in isolation, a suite of **unit and mock tests using `pytest`** will be developed in the `tests/` directory. These tests would:

*   **Target Individual Python Functions/Classes**: Focus on `devws_cli` modules, testing their logic independently of external commands.
*   **Mock External Commands**: Use `pytest-mock` or Python's `unittest.mock` to replace calls to `subprocess.run` (which executes `git`, `gcloud`, `gsutil`, etc.) with mock objects. This allows controlling the return values and side effects of these commands without actually executing them.
*   **File System Isolation**: Leverage `pytest`'s `tmp_path` fixture to provide a temporary, isolated file system for each test, simulating the user's home directory (`~`), global config directory (`~/.config/devws`), and current working directory without touching actual files.
*   **Test Setup Process Isolation**: Specifically for the `devws setup` command, `pytest` would enable testing various scenarios (e.g., config file existence, GCS responses, component failures) in a controlled manner, asserting internal state changes and `_log_step` calls without full system impact.

**Running Unit/Mock Tests:**

To run these tests, first install the test dependencies from the project root:

```bash
cd /path/to/ws-sync
pip install .[tests] # Installs devws and its test dependencies
pytest tests/
```

## Environment Variables for Test Overrides

The `devws` CLI provides environment variables to override default behaviors, facilitating isolated testing:

| Environment Variable          | Purpose                                                                                                                                              | Example Usage                                                               |
| :---------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------- |
| `WS_SYNC_CONFIG`              | Specifies the path to the global configuration file. Overrides the default `~/.devws/config.yaml`. Used to point to a temporary config file for tests. | `export WS_SYNC_CONFIG=/tmp/devws_test_config_XXXX.yaml`                    |
| `DEVWS_WS_SYNC_LABEL_KEY`     | Overrides the default `ws-sync` label key used by the CLI for applying/checking resource labels. Set to `ws-sync-test-case` for testing.              | `export DEVWS_WS_SYNC_LABEL_KEY=ws-sync-test-case`                          |
| `PROJ_LOCAL_CONFIG_SYNC_PATH` | Overrides the current working directory for `local` commands (push/pull/init) and the location of the `.ws-sync` file.                             | `export PROJ_LOCAL_CONFIG_SYNC_PATH=/tmp/devws_test_X`                      |

---

## Further Test Documentation

For specific integration test case details, refer to the individual shell scripts in the `integration-tests/` directory.

*   `integration-tests/test-case-1.sh` - Basic setup and local sync tests.
*   `integration-tests/test-gcs-restructure.sh` - Tests for new GCS bucket structure and migration logic.
*   ... (and other `test-case-*.sh` scripts)

## Manual Test Cases

### Test Case: Custom Component Registration and Backup/Restore

This test verifies the end-to-end flow of registering a custom Python component, backing up the configuration, and restoring it in an isolated environment.

**Steps:**

1.  **Create a dummy component script:**
    ```bash
    echo '#!/usr/bin/env python3
    print("This is a dummy component.")' > dummy_component.py
    ```

2.  **Register the new component:**
    This command should upload the `dummy_component.py` script to GCS and update the local `~/.config/devws/config.yaml` to include it.
    ```bash
    devws user-config component-add --id dummy-component --local-script-path dummy_component.py
    ```

3.  **Verify component readiness:**
    The new component should now be listed as 'READY' because its script exists in the local component cache.
    ```bash
    devws setup --dry-run
    ```

4.  **Simulate a clean environment:**
    Run `devws setup --dry-run` with `WS_SYNC_CONFIG` pointing to a non-existent file. This simulates a fresh setup where the global config hasn't been downloaded yet. The component should *not* be listed.
    ```bash
    export WS_SYNC_CONFIG_BAK=$WS_SYNC_CONFIG
    export WS_SYNC_CONFIG=/tmp/random12343/config.yaml
    devws setup --dry-run
    ```

5.  **Backup the configuration to GCS:**
    This command reads the user's local `~/.config/devws/config.yaml` and saves it to a known location in GCS.
    ```bash
    devws config backup
    ```

6.  **Simulate restore on a new machine:**
    Running `devws setup` in the "clean" environment (with the temporary `WS_SYNC_CONFIG`) will now:
    a. Download the `config.yaml` from GCS (because `WS_SYNC_CONFIG` points to a non-existent file).
    b. Download the `dummy-component.py` script from GCS (because it's listed in the just-downloaded config).
    c. The component should now be listed as 'READY'.
    ```bash
    devws setup --dry-run
    ```
7.  **Cleanup:**
    ```bash
    export WS_SYNC_CONFIG=$WS_SYNC_CONFIG_BAK
    rm dummy_component.py
    # You may also want to manually remove the component from the config
    # and GCS for a complete cleanup.
    ```