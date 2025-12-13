# Linux Development Workstation Config & Sync CLI

`devws` is a comprehensive command-line interface designed to streamline the setup of your Linux development environment and manage project-specific configurations across multiple workstations. It unifies core workstation setup tasks with intelligent, project-scoped configuration synchronization.

## Project Status and Alternatives

This project is an opinionated tool built to solve a specific developer's workflow. Its use case and unique value proposition have yet to be thoroughly investigated and evaluated against the many excellent, mature alternatives in the developer tooling ecosystem.

For a detailed analysis of how `devws` compares to mainstream tools like Chezmoi, Ansible, and others, please see the **[analysis of alternatives](ALTERNATIVES.md)**.

## 🔬 Research Branch

The `research` branch contains exploratory documentation and research on topics like:
- ChromeOS/Crostini terminal integration
- CLI tooling options (markdown viewers, SMS automation, etc.)
- Platform-specific workflows

These topics may eventually become features or documentation in `main`, but are kept in `research` while being explored. Check the branch periodically for useful findings.

## ✨ Features

### Core Workstation Configuration (`devws` commands)
- **🔄 Idempotent Setup**: `devws setup` can be run repeatedly to set up, extend, or repair your environment without issues.
- **🔐 Secure Cloud Sync & Backup**: `devws` provides multiple mechanisms to keep your environment safe and consistent, using Google Cloud as a backend. This includes full home directory backups, synchronization of specific dotfiles, and management of the tool's own configuration.
- **🛠️ Tool Installation**: Automates installation of essential CLIs (GitHub, Google Cloud, Cursor, Gemini) and language runtimes (Python, Node.js).
- **⚙️ Configurable**: Customize setup via a `config.yaml` file.

### Project-Level Configuration Management (`devws local` commands)
- **🚀 Project-Scoped Sync**: `devws local pull/push` synchronize project-specific, non-version-controlled files (like `.env` or local config) via Google Cloud Storage (GCS).
- **🧠 Git-Aware**: Automatically identifies project context (owner/repo) from Git for GCS pathing.
- **🛡️ .gitignore Integration**: Warns if managed files are not in `.gitignore` to prevent accidental commits of sensitive data.
- **📊 Status Checks**: `devws local status` provides an overview of local vs. GCS file status.

## 🚀 Installation

### Option 1: Install from Local Repository (Recommended for Development)

If you have cloned this repository locally:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/krisrowe/ws-sync.git
   cd ws-sync
   ```

2. **Install using pipx (recommended):**
   ```bash
   pipx install --editable .
   ```
   
   This installs `devws` in an isolated environment while keeping it editable, so code changes are immediately reflected.

3. **Run the initial workstation setup:**
   ```bash
   devws setup
   ```

### Option 2: Install Without Local Repository

If you don't have the repository cloned:

1. **Try installing with pip:**
   ```bash
   pip install git+https://github.com/krisrowe/ws-sync.git
   ```

2. **If you encounter an "externally-managed-environment" error:**
   
   Modern Python installations prevent system-wide package installation. Use pipx instead:
   
   ```bash
   pipx install git+https://github.com/github-user/ws-sync.git
   ```

### Verifying Installation

Check that `devws` is installed correctly:
```bash
devws --help
devws local pull --help
```
    This will guide you through setting up your core development environment.

## 📁 How It Works

`devws` operates on a few key files and concepts:

*   **Shell Integration**: Running `devws setup` will integrate a startup script into your shell (e.g., `~/.bashrc`). This script manages your `PATH`, NVM, and other environment needs on every new terminal session.
*   **Global Configuration (`~/.config/devws/config.yaml`)**: This is your personal, central configuration file for `devws`. You can edit it to define which setup components to run, which dotfiles to sync, and how backups should behave.
*   **Project-Specific Sync File (`.ws-sync`)**: When you run `devws local init` in a project directory, it creates this file. You list project-specific files (like a project's `.env`) here to be managed by `devws local push` and `pull`.

## 🌳 CLI Command Tree

```
devws
├── setup [OPTIONS]
│   └── Initializes or updates the core workstation configuration
│
├── config
│   ├── view
│   ├── set <key> <value>
│   ├── set-profile <profile>
│   ├── backup
│   └── restore
│
├── local
│   ├── init
│   ├── pull [--force] [--dry-run] [--json] [--debug]
│   ├── push [--force] [--debug]
│   └── status [--debug] [--all]
│
├── home
│   ├── backup
│   └── dotfiles
│       ├── status
│       ├── push
│       └── pull
│
├── secrets
│   ├── get <secret-name>
│   └── put <secret-name> <secret-value>
│
├── repo
│   └── user-archive [--target-folder <path>] [--no-bundle] [--dry-run]
│
└── precommit
    └── Scans for sensitive information
```

## 🎯 Usage

### 1. Core Workstation Configuration (`devws` commands)

These commands manage your overall development workstation setup and global `devws` configuration.

*   **`devws setup`**: Runs the full setup process for your Linux development environment. It's idempotent and self-healing.
    ```bash
    devws setup [--force]
    ```
    *   `--force`: Force re-run of setup steps, even if already verified.

*   **`devws clean`**: Cleans up temporary files (e.g., `*.backup.*`) across your workstation.
    ```bash
    devws clean
    ```

*   **`devws config`**: Manages the `devws` tool's own global configuration (`~/.config/devws/config.yaml`).
    *   **`devws config view`**: Displays the current global `devws` configuration.
        ```bash
        devws config view
        ```
    *   **`devws config set <key> <value>`**: Sets a specific global configuration key.
        ```bash
        devws config set default_gcs_profile my-personal-profile
        devws config set gcs_profiles.my-personal-profile.project_id my-gcp-project
        ```
    *   **`devws config set-profile <profile_name>`**: Sets the default GCS profile.
        ```bash
        devws config set-profile work-profile
        ```
    *   **`devws config backup`**: Backs up the `devws` tool's configuration (`~/.config/devws/config.yaml` and potentially other assets) to GCS.
        ```bash
        devws config backup [--profile <profile_name>]
        ```
    *   **`devws config restore`**: Restores the `devws` tool's configuration from GCS.
        ```bash
        devws config restore [--profile <profile_name>] [--force]
        ```

*   **`devws home`**: Manages your user's home directory.
    *   **`devws home backup`**: Creates a full, versioned backup of your home directory (excluding configured patterns) to local storage or GCS.
        ```bash
        devws home backup [--profile <profile_name>]
        ```
    *   **`devws home dotfiles`**: Manages synchronization of specific dotfiles and configuration files.
        *   **`devws home dotfiles push`**: Pushes configured dotfiles from local to GCS.
            ```bash
            devws home dotfiles push [--profile <profile_name>]
            ```
        *   **`devws home dotfiles pull`**: Pulls configured dotfiles from GCS to local.
            ```bash
            devws home dotfiles pull [--profile <profile_name>] [--force]
            ```

### 2. Project-Level Configuration Management (`devws local` commands)

These commands manage project-specific, non-version-controlled files (like `.env` files for a particular project) using Google Cloud Storage (GCS). These commands should be run from within a Git repository.

*   **`devws local init`**: Initializes a `.ws-sync` file in the current Git repository. This file defines which project-specific files are managed by `devws local`.
    ```bash
    devws local init
    ```

*   **`devws local pull`**: Pulls all files listed in `.ws-sync` from GCS to the local project directory.
    ```bash
    devws local pull [--force] [--dry-run] [--json]
    ```
    *   `--force`: Overwrite local changes if conflicts exist.
    *   `--dry-run`: Perform a dry run without actually pulling files, showing what would happen.
    *   `--json`: Output dry run results as JSON.

*   **`devws local push`**: Pushes all files listed in `.ws-sync` from the local project directory to GCS.
    ```bash
    devws local push [--force]
    ```
    *   `--force`: Overwrite GCS version if conflicts exist.

*   **`devws local status`**: Shows the synchronization status of managed files (local vs. GCS) and checks against `.gitignore`.
    ```bash
    devws local status [--all]
    ```
    *   `--all`: List files ignored by `.gitignore` but not in `.ws-sync`.

### 3. Repository-Level Commands (`devws repo` commands)

These commands operate on a git repository as a whole.

*   **`devws repo user-archive`**: Creates a self-contained archive of user-specific files and the git repository itself.

    ```bash
    devws repo user-archive --target-folder <path> [--no-bundle] [--dry-run]
    ```
    *   `--target-folder`: Local directory to save the archive (required).
    *   `--no-bundle`: Exclude the git bundle from the archive.
    *   `--dry-run`: Show what would be archived without creating the file.

    **What gets archived:**

    1. **Git bundle** (`repo.bundle`): A complete clone of the repository including all commits, branches, and tags. This is equivalent to what you'd get from `git clone` - no untracked files, no gitignored files, no credentials.

    2. **User files**: Files matching patterns listed under the `# user-files` section in `.gitignore`. These are the local, non-versioned files specific to your use of the repository.

    3. **Git remotes** (`git-remotes.txt`): Documents where the repository was hosted, for reference.

    **Why include the git bundle by default?**

    Many repositories are created primarily to support work on user-specific data files. Without the associated code and tooling, those user files may become meaningless. Including the bundle ensures the archive remains useful even if:
    - The remote repository is later deleted
    - The hosting account becomes inaccessible
    - You need to restore the complete working environment

    **Setting up user-files in .gitignore:**

    Add a `# user-files` section to your `.gitignore`:

    ```gitignore
    # user-files
    config.yaml
    user-*.*
    ```

    Files matching these patterns will be included in the archive. The section ends at the next blank line or end of file.

    **Example usage:**

    ```bash
    # Preview what would be archived
    devws repo user-archive --target-folder . --dry-run

    # Create archive in current directory
    devws repo user-archive --target-folder .

    # Create archive without git bundle (user files only)
    devws repo user-archive --target-folder ./backups --no-bundle
    ```

#### <a name="repo-identification"></a>How your project's local-only config files are tied back to your repository

When you run `devws local push` or `devws local pull`, the tool needs a unique and consistent way to identify your project's backup in your GCP project. This ensures that when you restore your configuration on a different machine, you get the correct files for the correct project.

`devws` achieves this by using the following Git command:

```bash
git config --get remote.origin.url
```

This command reads the URL of your repository's `origin` remote directly from your local Git configuration, which is stored in the `.git/config` file within your repository's directory. This URL serves as the unique identifier to construct the path for your backup in your GCP project.

This approach ensures that as long as your repository is cloned from the same remote source, `devws` will always be able to locate its corresponding backup in your GCP project.

### 3. Advanced Usage: Backing Up Local-Only Repositories (Interim Solution)

In some cases, you may want to use `devws local` to back up project folders that contain sensitive or customer-specific information without pushing the entire project to a public or private git hosting service. For example, you might have a local folder (e.g., `~/ClientX`) with customer-specific configurations and tools that you want to keep synchronized across your workstations but not on GitHub.

Since `devws local push` requires a git remote origin URL to determine the GCS path, you have a few options to satisfy this requirement for a local-only repository.

#### Option 1: Use a "Fake" Remote URL (Recommended)

This is the recommended workaround. It involves creating a "fake" remote URL that doesn't need to exist but must be in a format that `devws` can parse (e.g., `https://<hostname>/<owner>/<repo-name>.git`).

**Steps:**

1.  **Initialize a git repository** in your local-only folder:
    ```bash
    cd ~/ClientX
    git init
    ```

2.  **Add a fake remote origin**. Using a fake host name and owner can help avoid confusion with real repositories.
    ```bash
    git remote add origin https://local-only.devws/fake-account-local-only/ClientX-config.git
    ```

3.  **Create a `.gitignore` file** to exclude any sensitive subfolders that you don't want to back up to GCS.

4.  **Create a `.ws-sync` file** and list the files and folders you want to back up to GCS.

5.  **Run `devws local push`**:
    ```bash
    devws local push
    ```

This will back up the files and folders listed in `.ws-sync` to GCS under the path `repos/fake-account-local-only/ClientX-config/`.

#### Interim Solution: Manual `git bundle` Backup

Pending the implementation of the `devws bundle` commands, you can manually perform a bundle backup of a local-only repository. This is the recommended approach for backing up versioned, sensitive, or customer-specific repositories.

**Steps:**

1.  **Navigate to your local git repository**:
    ```bash
    cd ~/ClientX-project
    ```

2.  **Create the bundle file** in a temporary directory:
    ```bash
    mkdir -p /tmp/devws-bundles
    git bundle create /tmp/devws-bundles/ClientX-project.bundle --all
    ```
    *   `--all` ensures all branches and tags are included in the bundle.
    *   The bundle file is named after the project directory for easy identification.

3.  **Upload the bundle to GCS**:
    ```bash
    gsutil cp /tmp/devws-bundles/ClientX-project.bundle gs://your-bucket/bundles/
    ```
    *   We recommend using a dedicated `bundles/` folder in your GCS bucket to store these backups.

4.  **To restore the repository**:
    ```bash
    # Download the bundle from GCS to a temporary folder
    gsutil cp gs://your-bucket/bundles/ClientX-project.bundle /tmp/devws-bundles/

    # Clone the repository from the bundle
    git clone /tmp/devws-bundles/ClientX-project.bundle
    ```

This manual process provides a robust way to back up your entire local-only git repositories to GCS. For more details on this proposed feature, see the [Future Enhancements](#-future-enhancements) section.

#### Option 2: Use a Custom Git Config Variable

As an alternative to a fake remote, you could use `git config` to set a custom variable that `devws` could be enhanced to read. This is not currently implemented but is a potential future enhancement.

#### Option 3: Use the Local Directory Name

Another potential future enhancement is for `devws` to use the name of the local directory as the repository name if no remote origin is found. This would simplify the process for local-only repositories.

This workaround is an interim solution. For a more integrated approach, see the proposed `--local-only` flag in the [Future Enhancements](#-future-enhancements) section.

## ⚙️ Configuration

### Repository Configuration (config.yaml)
The `devws setup` command uses a configuration system to let you customize what gets installed. Copy `config.yaml.example` to `config.yaml` in the repository root and customize:

```yaml
# Example configuration for devws CLI
#
# This file defines the components and their configurations for your development workstation setup.
# You can enable or disable specific components and customize their settings.

components:
  github:
    enabled: true
  google_cloud_cli:
    enabled: true
  python:
    enabled: true
    min_version: "3.9"
  nodejs:
    enabled: true
    min_version: "20"
  cursor_agent:
    enabled: true
  gemini_cli:
    enabled: true
  env_setup:
    enabled: true
  proj_local_config_sync:
    enabled: true
    local_sync_candidates:
      - "*.env"
      # Add other files/patterns to synchronize with GCS here
      # Example:
      # - "my_project_config.json"
      # - "secrets/*.txt"
    bucket_name: "" # Your Google Cloud Storage bucket name for synchronization

# Global settings (not tied to a specific component)
project_id: "" # Your Google Cloud Project ID (used for secrets backup validation)
```

### Project-Specific Configuration (`.ws-sync`)
For `devws local` commands, create a `.ws-sync` file in the root of your Git repository. This file lists the project-specific files you want to manage.

```
# This file specifies project-specific files that should be synchronized
# across workstations for the same developer/user via the 'devws local' utility.
#
# IMPORTANT: All files listed here should also be included in your project's .gitignore
# to prevent accidental version control of sensitive or local-only configurations.
#
# Example:
# .env
# my-local-config.json
#
```

## 🎯 Prerequisites

-   **Linux** (Debian-based distributions recommended, e.g., Debian, Ubuntu, or ChromeOS with Linux development environment)
-   **Internet connection** for downloading tools and packages
-   **GitHub account** (for SSH key setup and authentication)
-   **Google Cloud account** (optional, for `devws env` and `devws local` functionality)
-   **Python 3.7+** (for running the `devws` CLI)

## 🤝 Contributing

This is a personal development environment setup. If you find issues or want to suggest improvements:

1.  **Create an issue** - Report bugs or request features
2.  **Fork and submit PR** - Contribute code improvements
3.  **Share feedback** - Let me know what works well or needs improvement

## Configuration

The `devws` CLI uses a global configuration file to manage GCS profiles and other settings.

*   **Default Location:** `~/.config/devws/config.yaml`
*   **Environment Variable:** `WS_SYNC_CONFIG`
    *   You can override the directory where `devws` looks for its configuration by setting the `WS_SYNC_CONFIG` environment variable.
    *   Example: `export WS_SYNC_CONFIG=/path/to/custom/config/dir`
    *   The CLI will look for `config.yaml` inside this directory.

## 🔮 Future Enhancements

- **Direct GitHub Installation**: Simplify installation with a single command (similar to `npx`) that doesn't require cloning the repository first
- **PyPI Publishing**: Publish to PyPI for easier installation via `pip install devws`
- **Auto-update Mechanism**: Built-in command to update `devws` to the latest version
- **Smart Management of Non-Portable Home Files**: For configuration files that are largely machine-specific (e.g., `~/.bashrc`, `~/.env`), implement functionality to manage specific entries or sections within the file, rather than overwriting the entire file. This would ensure portability of desired settings while respecting local system configurations.
- **User Home Configuration Synchronization (Design Tension)**: While backup/restore of the `devws` tool's own configuration (`~/.config/devws/`) is planned, a generic solution for synchronizing arbitrary user home directories (e.g., `~/my-dev-folder/`) presents significant design challenges (e.g., merge conflicts, sensitive data handling, platform differences). This might best be addressed not by monolithic directory backups, but through optional or custom components that provide fine-grained, user-defined synchronization logic for specific files or subdirectories.
- **Local-Only Repository Synchronization**: Introduce a `--local-only` flag to `devws local init`. This would configure a local git repository for GCS synchronization without requiring a real remote git repository. It would automatically register a fake remote origin (e.g., `https://local-only.devws/fake-account-local-only/<repo-name>.git`) to satisfy the GCS pathing logic, making it easier to back up local-only projects with sensitive information.
- **Git Bundle Backup for Local-Only Repositories**: Introduce a new set of commands, `devws bundle push` and `devws bundle pull`, as an alternative to `devws local` for backing up "local-only, config-only" repositories. This would be for use cases where the entire repository (i.e., the versioned files) should be backed up, not just the unversioned configuration files.
    -   **Mechanism**: Use `git bundle create` to create a single, compressed bundle file of the repository in a temporary folder.
    -   **Storage**: Store the bundle files in a dedicated GCS folder, such as `gs://my-bucket/bundles/`.
    -   **Identification**: To identify which bundle file in GCS corresponds to a given local repository, `devws bundle` would use the git remote origin URL as a key, similar to `devws local`. A unique name for the repository could also be registered as metadata within the local `.git` database using `git config devws.bundle-name <unique-name>`.
    -   **Restore**: `devws bundle pull` would download the bundle file to a temporary folder and then use `git clone` to restore the repository.

## 🧪 Testing

For details on the testing strategy, including integration tests (in `integration-tests/`) and a future plan for unit/mock testing with Pytest, please refer to the [TESTING.md](TESTING.md) document.

## 📄 License

This project is for personal use. Feel free to adapt it for your own development environment setup.

---

**Note**: This CLI is designed for Linux development environments. It works on any Linux distribution with Python 3.7+ and standard package managers.

---

## Appendix: Design Notes

### Backup vs. Sync: An Unresolved Design Tension

A thoughtful design question has been raised regarding the overlapping nature of the various backup and sync commands. This is an open topic for future refinement.

**The Current State & The "Superset" Problem:**

The current command structure creates a situation where different commands can back up the same file to different locations, creating potential confusion:
-   `devws config backup` backs up `~/.config/devws/config.yaml` to `gs://.../devws/`.
-   `devws home dotfiles push` could be configured to also back up `~/.config/devws/config.yaml` to `gs://.../home/dotfiles/`.
-   `devws home backup` will *definitely* back up `~/.config/devws/config.yaml` as part of its full home directory archive to `gs://.../home/backups/`.

This leads to a valid question: "Where is my latest backup of a specific file?"

**Argument for Separate Commands (Current Design):**

The current design intentionally separates the *concepts* of **Archiving** and **Syncing**.
-   **`devws home backup` (Archiving)**: Creates a full, point-in-time, versioned `.zip` file. This is for disaster recovery. You restore the whole system from a single snapshot in time.
-   **`devws home dotfiles` & `devws config` (Syncing)**: Manages a "live," canonical copy of individual configuration files. This is for keeping the state of multiple workstations consistent. You pull the latest `config.yaml` to a new machine to get it configured.

In this model, you wouldn't typically use the full `home backup` to find your latest `config.yaml`; you would use `devws config restore`. The full backup is a safety net, not a state management tool.

**Argument for Consolidated Commands:**

As was suggested, an alternative would be to consolidate these into fewer commands, for example:
-   `devws backup --scope=home` (Full backup)
-   `devws backup --scope=dotfiles` (Sync dotfiles)
-   `devws backup --scope=tool-config` (Sync tool config)

The major pro is a single, unified `backup` command. The major con is that it conflates the very different operations of "creating a versioned archive" and "syncing live files," which could be equally confusing.

This remains an unresolved design tension. The current separation is explicit but requires the user to understand the conceptual difference. A consolidated command might be simpler at first glance but could hide important distinctions. Future versions of `devws` may revisit this design.
