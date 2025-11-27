# Project TODO List

This document outlines the remaining tasks to complete the integration of the 'stuff/' directory content and transition to a Python-based CLI (`devws`).

## Architectural Transition: Python-based CLI (`devws`)

The core functionality of the repository is being transitioned from shell scripts and Makefiles to a unified Python-based CLI named `devws`.

### Current Status:
- `devws_cli` Python project structure is created.
- `devws` CLI is installed locally and the `setup`, `env` (backup/restore), `local` (pull/push/status/init), and `clean` commands are implemented in `devws_cli/cli.py`.

## Remaining Tasks:

### 1. Finalize `devws` CLI Implementation & Testing

- [x] **Implement `devws config` command:**
    - [x] Create a new command group `devws config`.
    - [x] Implement subcommands (e.g., `devws config set profile <name>`) to modify the `default_gcs_profile` in `~/.config/devws/config.yaml`.
    - [x] Implement a subcommand (e.g., `devws config view`) to display the current global config.
    - [x] **Note:** The global config should control the GCS profile for all commands on the current workstation. It is not configurable on a per-repo basis. It will default to "default" unless explicitly changed via `devws config` command.
- [x] **Enhance `devws setup`:**
    - [x] Add a step to check for `~/.config/devws/config.yaml`.
    - [x] If it doesn't exist, create the `~/.config/devws` directory.
    - [x] Copy `config.default.yaml` from the repo to `~/.config/devws/config.yaml` during `devws setup`.
    - [x] Log this action.
- [x] **Implement Global `devws` Configuration:** (Partially done in `utils.py`, but needs to be integrated with `devws setup` for creation)
    - [x] Create a mechanism to load global `devws` configuration (e.g., from `~/.config/devws/config.yaml`).
    - [x] Define a list of `local_sync_candidates` in this global config (e.g., `.env`, `config.local.json`).
    - [x] Consider other global configuration options: default GCS profile, default `PROJECT_ID`, logging level, preferred editor.
- [x] **Enhance `devws local init` logic:**
    - [x] When creating `.ws-sync`, automatically include file names from the global `local_sync_candidates` list that are also present in the current repository's `.gitignore` file.
    - [x] Report these added files as command-line output.
    - [x] Ensure `.env` is included in the default global `local_sync_candidates`.
- [x] **Modify `devws_cli/local_commands.py`:**
    - [x] Remove the `--profile` option from `pull`, `push`, `status`, `init` commands.
    - [x] These commands should now *always* use the `default_gcs_profile` loaded from the global config.
- [x] **Implement `devws local pull` logic:** Pulls all files listed in `.ws-sync` from GCS to local.
- [x] **Implement `devws local push` logic:** Pushes all files listed in `.ws-sync` from local to GCS.
- [x] **Implement `devws local status` logic:** Shows sync status of managed files.
- [x] **Implement `devws local clear` logic:** Deletes all project-scoped files for the current repository from GCS. This will be a destructive command requiring user confirmation.
- [x] **Review and Refine `devws_cli/cli.py` and `devws_cli/utils.py`:**
    - Ensure all logic from original `setup.sh`, `secrets.sh`, and `stuff/Makefile` (for GCS sync) is accurately translated and robust.
    - Add comprehensive error handling and user feedback.
- [x] **Add Unit/Integration Tests:** Create tests for the `devws` CLI commands to ensure correctness and prevent regressions.

### 2. Repository Cleanup and Documentation

- [ ] **Create `archive/` directory:** Create a new directory in the repository root for historical files.
- [ ] **Move `stuff/Makefile` to `archive/stuff_Makefile.bak`:** Preserve the original `stuff/Makefile` as an artifact.
- [ ] **Move `stuff/README.md` to `archive/stuff_README.md.bak`:** Preserve the original `stuff/README.md` as an artifact.
- [ ] **Remove `stuff/` directory:** Delete the now-empty `stuff/` directory.
- [ ] **Remove original `Makefile`:** The root `Makefile` is superseded by the `devws` CLI.
- [ ] **Remove original `setup.sh`:** Its logic is now in `devws_cli/cli.py`.
- [ ] **Remove original `secrets.sh`:** Its logic is now in `devws_cli/cli.py`.
- [ ] **Rewrite main `README.md`:**
    - Document the new `devws` CLI, its installation, and usage.
    - Clearly differentiate Core vs. Ad-Hoc configurations.
    - Incorporate relevant content from the original `README.md` and `stuff/README.md`.
    - Update the "File Structure" section.
    - Include steps to install `devws` locally with or without the repo's source code being git cloned to a local workspace, if possible and easy.
- [ ] **Update `setup.py` `long_description`:** Point to the new main `README.md`.

## Future Enhancements:

These are valuable ideas for future development to make `devws local` even more intelligent and user-friendly.

- [ ] **Intelligent Workspace Scanning:**
    - Implement functionality to scan a workspace for files that are good candidates for `devws local` management (e.g., `.env`, `config.json`, `settings.py`).
    - Provide suggestions to the user during `devws local init` or `status`.
- [ ] **Advanced Sync Status Validation:**
    - Enhance `devws local status` to compare local file content/hashes with GCS versions without pulling/pushing.
    - Warn the user if local configurations are out of sync with their GCS backups.
- [ ] **Exclusion Patterns in `.ws-sync`:**
    - Support exclusion patterns (e.g., `!.env`) in `.ws-sync` to explicitly prevent warnings or suggestions for certain files, even if they match global candidates.
- [ ] **Backup/Restore of `~/.config/devws/config.yaml` and GitHub/SSH Configurations:**
    - Analyze the viability and appropriateness of incorporating backup/restore functionality for `~/.config/devws/config.yaml` contents, GitHub authentication configurations, and SSH keys. This would involve considering what aspects are valuable, viable, and appropriate for automated management.
- [ ] **`devws home dotfiles` command:**
    - Create a new command group `devws home dotfiles` to manage non-repo-specific local configuration files.
    - This command should manage files like `~/.env`, `~/.gemini/GEMINI.md`, and ssh keys.
    - [x] Implement `devws home dotfiles status` to show whether these files are backed up to GCS.
    - [x] Implement `devws home dotfiles push` to back up these files to GCS.
    - [x] Implement `devws home dotfiles pull` to restore these files from GCS.
    - The `pull` command should be non-destructive and should not overwrite local files with pending changes. It should inform the user about the conflicts and provide a way to resolve them.
- [ ] **Categorized Setup Output with Centralized Reporting:**
    - Refactor the setup component architecture to use a centralized reporting system.
    - Components should return status and messages (array of guidance/errors/warnings) instead of directly calling `_log_step`.
    - The main `setup_commands.py` loop should collect these results and control formatting/grouping.
    - Add optional `category` attribute to components in `config.yaml` (e.g., "core", "common", "development", "custom").
    - Group components by category in the final SETUP REPORT table with subheadings.
    - Display components in order: Core, Common, Development, Custom.
    - This will provide better separation of concerns and more flexible output formatting.
- [x] **Refactor and de-duplicate helper functions:**
    - The helper functions `_get_file_hash`, `_get_gcs_file_status`, `_get_local_file_status`, and `_generate_ascii_table` were successfully moved to `utils.py` to be used by both `local_commands.py` and `home_commands.py`.
    - All command implementations have been restored and updated to use the centralized helper functions.
- [ ] **Review ALTERNATIVES.md to establish project clarity:**
    - Analyze the newly created `ALTERNATIVES.md` file.
    - Use the analysis to refine the project's mission, scope, and unique value proposition in the `README.md`.
- [ ] **Research GitHub Codespaces / Dev Containers for integration opportunities:**
    - Investigate how `devws` could be used to bootstrap or manage a cloud-based development environment defined by `devcontainer.json`.
    - Explore if `devws` can complement or simplify the setup within a Codespace.
- [ ] **Expand `devws config backup` to include the entire `~/.config/devws` directory:**
    - The `devws config backup` command currently only backs up the `config.yaml` file.
    - This should be expanded to back up the entire `~/.config/devws` directory, including any custom component scripts, the `startup.sh`, and other assets. This would be a recursive directory backup to GCS.
- [x] **Implement `devws precommit` command:**
    - Create a new command to scan local files for sensitive information.
    - **Scope**: Scan all tracked files and all untracked (non-ignored) files.
    - **Dynamic Sensitive Strings**:
        - Automatically derive sensitive values like the username (from `/home/[username]`), user's first/last names (from `git config user.name`), and user's email (from `git config user.email`).
        - Automatically parse `.env` files in the project to extract sensitive values.
    - **Configurable Patterns**: Allow users to define custom regex patterns in a `precommit.unsafe_patterns` list within `~/.config/devws/config.yaml`. The default config will keep this list empty.
    - **Built-in Generic Patterns**: Include checks for common secret formats (AWS keys, Stripe keys, private keys, high-entropy strings) loaded from `unsafe-patterns.yaml`.
    - **Reporting**: Report the sensitive value, file path, line number, and the line content where it was found.