# devws - ChromeOS Development Workstation Setup & Project Configuration CLI

`devws` is a comprehensive command-line interface designed to streamline the setup of your ChromeOS development environment and manage project-specific configurations across multiple workstations. It unifies core workstation setup tasks with intelligent, project-scoped configuration synchronization.

## ✨ Features

### Core Workstation Configuration (`devws` commands)
- **🔄 Idempotent Setup**: `devws setup` can be run repeatedly to set up, extend, or repair your environment without issues.
- **🔐 Secure Global .env Management**: `devws env backup` and `devws env restore` securely manage your global `~/.env` file using Google Secrets Manager.
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
   git clone https://github.com/github-user/ws-sync.git
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
   pip install git+https://github.com/github-user/ws-sync.git
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

## 📁 File Structure

```
ws-sync/
├── devws_cli/            # Python package for the devws CLI
│   ├── __init__.py
│   ├── cli.py            # Main CLI entry point
│   ├── setup_commands.py # Logic for 'devws setup'
│   ├── env_commands.py   # Logic for 'devws env' group (backup/restore)
│   ├── local_commands.py # Logic for 'devws local' group (pull/push/status/init)
│   └── clean_commands.py # Logic for 'devws clean'
├── archive/              # Historical files (e.g., original Makefiles, READMEs)
├── config.yaml.example   # Configuration template for 'devws setup'
├── env.example           # Environment variables template
├── .gitignore            # Git ignore rules for the devws repo itself
├── MERGE-ANALYSIS.md     # Analysis of the merge process
├── README.md             # This file
├── setup.py              # Python package setup file
├── ALT-DESIGN.md         # Alternative design considerations for workstation sync
└── DESIGN.md             # Technical design document for workstation sync

# External files (created by devws setup or local commands):
~/.env                   # Your global environment variables (managed by 'devws env')
~/.config/devws/config.yaml # Your global configuration file for 'devws setup' (gitignored)
./.ws-sync               # Project-specific files to manage (for 'devws local')
```

## 🎯 Usage

### 1. Core Workstation Configuration (`devws` commands)

These commands manage your overall development workstation setup.

*   **`devws setup`**: Run the full setup process for your ChromeOS development environment. It's idempotent and self-healing.
    ```bash
    devws setup [--force] [--config-path <path>]
    ```
    *   `--force`: Force re-run of setup steps, even if already verified.
    *   `--config-path`: Specify a custom `config.yaml` file.

*   **`devws env backup`**: Backs up your global `~/.env` file to Google Secrets Manager.
    ```bash
    devws env backup
    ```

*   **`devws env restore`**: Restores your global `~/.env` file from Google Secrets Manager.
    ```bash
    devws env restore
    ```

*   **`devws clean`**: Cleans up temporary files (e.g., `*.backup.*`) across your workstation.
    ```bash
    devws clean
    ```

### 2. Project-Level Configuration Management (`devws local` commands)

These commands manage project-specific, non-version-controlled files (like `.env` files for a particular project) using Google Cloud Storage (GCS). These commands should be run from within a Git repository.

*   **`devws local init`**: Initializes a `.ws-sync` file in the current Git repository. This file defines which project-specific files are managed by `devws local`.
    ```bash
    devws local init [--profile <profile_name>]
    ```
    *   `--profile`: Specifies the GCS profile to use (e.g., `default`, `personal`, `work`).

*   **`devws local pull`**: Pulls all files listed in `.ws-sync` from GCS to the local project directory.
    ```bash
    devws local pull [--profile <profile_name>] [--force] [--dry-run] [--json]
    ```
    *   `--profile`: Specifies the GCS profile to use.
    *   `--force`: Overwrite local changes if conflicts exist.
    *   `--dry-run`: Perform a dry run without actually pulling files, showing what would happen.
    *   `--json`: Output dry run results as JSON.

*   **`devws local push`**: Pushes all files listed in `.ws-sync` from the local project directory to GCS.
    ```bash
    devws local push [--profile <profile_name>] [--force]
    ```
    *   `--profile`: Specifies the GCS profile to use.
    *   `--force`: Overwrite GCS version if conflicts exist.

*   **`devws local status`**: Shows the synchronization status of managed files (local vs. GCS) and checks against `.gitignore`.
    ```bash
    devws local status [--profile <profile_name>]
    ```
    *   `--profile`: Specifies the GCS profile to use.

#### How `devws local` Identifies Your Repository {#repo-identification}

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

-   **ChromeOS** with Linux development environment enabled (Crostini)
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

**Note**: This CLI is specifically designed for ChromeOS development environments. While it may work on other Linux distributions, it's optimized for Crostini/gLinux VMs running on ChromeOS.
