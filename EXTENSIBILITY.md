# devws Extensibility Plan

This document outlines the plan for adding extensibility features to the `devws` CLI tool.

## Checklist of Tasks

## Configuration and Extensibility

### Core Principles
- **Unified Component Framework**: All setup steps, whether built-in or custom, are treated as Python module-based "components".
- **Explicit Configuration Management**: The `devws` tool's own configuration is managed explicitly by the user through a dedicated `devws config` command group, separate from the `devws setup` execution process.

### `devws config` Command Group
This group is the central point for managing the entire `devws` configuration.

- [ ] **`devws config init`**:
    - **Purpose**: For first-time users. Initializes a new, default local configuration.
    - **Action**: Creates the `~/.config/devws/` directory and populates it with a `config.yaml` file copied from the `devws_cli/config.default.yaml` template. Does not require GCS.

- [ ] **`devws config backup`**:
    - **Purpose**: Saves the user's complete `devws` configuration to the cloud.
    - **Action**: Uploads the entire `~/.config/devws/` directory (including `config.yaml` and the `components/` subdirectory) to `gs://<bucket>/user-home/.config/devws/`.

- [ ] **`devws config restore`**:
    - **Purpose**: Restores a user's `devws` configuration from the cloud to a new machine.
    - **Action**: Downloads the `devws/` directory from `gs://<bucket>/user-home/.config/devws/` and places it in `~/.config/`.

### `devws setup` Execution Flow
- [ ] **Pre-requisite**: `devws setup` will now require the `~/.config/devws/config.yaml` file to exist. If it is missing, the command will fail with a message instructing the user to run `devws config init` or `devws config restore`.
- [ ] **Execution**: Reads the `components` dictionary from the merged configuration and executes each enabled component's `setup()` function in the order of their `tier`.

### Custom Components as Python Modules
- [ ] **Location and Discovery**:
    - Users place their custom component Python modules (e.g., `my_corp_tool.py`) in `~/.config/devws/components/`.
    - `devws setup` discovers components from both the built-in `devws_cli/components/` directory and the user's `~/.config/devws/components/` directory.
- [ ] **Configuration**:
    - Custom components are enabled and configured in `~/.config/devws/config.yaml` under the `components` key, identically to built-in components. This eliminates the need for a separate `custom_components` list.
- [ ] **Python Module Requirements**:
    - Each component is a `.py` file containing a `setup(config, dry_run=False)` function.

### Secret Management
- [ ] For highly sensitive data (e.g., SSH private keys, API tokens), the `devws secrets` command group will be used to interact with Google Cloud Secret Manager, keeping this data separate from the GCS-based configuration backup.

### `devws setup --dry-run` Functionality
- [ ] **Implement `--dry-run` option**: Add a `--dry-run` flag to the `devws setup` command.
- [ ] **Pass `dry_run` flag**: The `devws setup` command will pass `dry_run=True` to the `setup()` function of *every* component.
- [ ] **Update `_run_command`**: This utility will be modified to accept a `dry_run` argument. If `True`, it will log the command it *would* have run and return a mock success. Idempotency checks within component `setup()` functions will call `_run_command` with `dry_run=False` to ensure they still execute.

## Implementation Notes
- Consider using a dedicated section in `config.yaml` for `install_steps` or similar.
- For `devws local status`, leverage `git check-ignore` and `git ls-files` for accurate `.gitignore` cross-checking.