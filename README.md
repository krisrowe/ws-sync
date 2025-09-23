# ChromeOS Development Environment Setup

A comprehensive, idempotent setup script for ChromeOS development environments (Crostini/gLinux VMs). This script can be run repeatedly without issues to set up, extend, or repair your development environment.

## ✨ Features

- **🔄 Idempotent**: Safe to run multiple times - detects existing installations
- **🛠️ Self-healing**: Can repair broken or partially configured environments  
- **🔐 Secure**: Uses standard `~/.env` file with Google Secrets Manager backup
- **📊 Smart Reporting**: Detailed status reporting with clear next steps
- **⚙️ Configurable**: Enable/disable features via `.config` file
- **🚀 ChromeOS Optimized**: Specifically designed for ChromeOS development

## 🚀 Quick Start

1. **Clone this repository:**
   ```bash
   git clone https://github.com/github-user/ws-sync.git
   cd ws-sync
   ```

2. **Run the setup:**
   ```bash
   make setup
   ```

That's it! The script will guide you through the entire setup process.

## 🛠️ What Gets Installed

### Core Development Tools
- **GitHub CLI** (`gh`) - Command-line interface for GitHub
- **Google Cloud CLI** (`gcloud`) - Google Cloud Platform tools
- **Node.js** (v20+) - JavaScript runtime via NVM
- **Python** (v3.9+) - Python interpreter and pip
- **Cursor Agent** - AI-powered code assistant
- **Gemini CLI** - Google's Gemini AI command-line tool

### Authentication & Security
- **SSH Key Generation** - Ed25519 key pair for GitHub authentication
- **GitHub Integration** - Automatic SSH key upload to GitHub
- **SSH Agent Setup** - Persistent SSH authentication
- **Environment Variables** - Secure `~/.env` file management

### Configuration Management
- **Shell Integration** - Automatic environment loading on startup
- **Google Secrets Manager** - Cloud backup/restore for environment variables
- **Configuration System** - Enable/disable features via `.config` file

## 📁 File Structure

```
ws-sync/
├── Makefile              # Build automation and shortcuts
├── setup.sh              # Main setup script
├── secrets.sh            # Google Secrets Manager backup/restore
├── .config.example       # Configuration template
├── env.example           # Environment variables template
├── .gitignore           # Git ignore rules
└── README.md            # This file

# External files (created by setup):
~/.env                   # Your environment variables (gitignored)
~/.config                # Your configuration file (gitignored)
```

## 🎯 Usage

### First Time Setup
```bash
git clone https://github.com/github-user/ws-sync.git
cd ws-sync
make setup
```

### Re-running Setup
```bash
cd ws-sync
make setup
```

The script intelligently detects what's already configured and only sets up missing components.

### Available Commands
```bash
make setup     # Run the full setup process
make backup    # Backup ~/.env to Google Secrets Manager
make restore   # Restore ~/.env from Google Secrets Manager
make clean     # Clean up temporary files
make help      # Show available commands
```

## ⚙️ Configuration

The setup script uses a configuration system to let you customize what gets installed:

### Configuration File
Copy `.config.example` to `.config` and customize:

```bash
# Core Tools
ENABLE_GITHUB_SETUP=true
ENABLE_GOOGLE_CLOUD_CLI=true

# Google Cloud Configuration
PROJECT_ID=your-gcp-project-id  # Required for secrets backup validation

# Development Languages
ENABLE_PYTHON=true
PYTHON_MIN_VERSION=3.9
ENABLE_NODEJS=true
NODEJS_MIN_VERSION=20

# CLI Tools
ENABLE_CURSOR_AGENT=true
ENABLE_GEMINI_CLI=true

# Environment Management
ENABLE_ENV_SETUP=true
```

### Environment Variables
The script creates a `~/.env` file for your API keys and configuration:

```bash
# Example ~/.env file
export GEMINI_API_KEY="your-gemini-api-key-here"
export CURSOR_API_KEY="your-cursor-api-key-here"
export NODE_ENV="development"
export DEBUG="true"
```

## 🔐 Secrets Management

### Local Environment File
- **Location**: `~/.env` (standard location for shell environment variables)
- **Purpose**: Store API keys, configuration, and environment variables
- **Loading**: Automatically loaded on shell startup via `.bashrc`

### Google Secrets Manager Integration
Backup and restore your environment variables to/from Google Cloud:

```bash
# Backup your ~/.env to Google Secrets Manager
make backup

# Restore from Google Secrets Manager
make restore
```

### Benefits
- **Standard Convention**: Uses `~/.env` file that works with most tools
- **Cloud Backup**: Secure backup/restore via Google Secrets Manager
- **Repository Clean**: Environment variables stay outside the repository
- **Cross-Project**: Works across multiple projects and repositories

## 📊 Status Reporting

The setup script provides detailed status reporting for each step:

### Status Types
- **✅ VERIFIED** - Found already done, no action taken
- **✅ COMPLETED** - Just finished doing this step
- **⏭️ SKIP** - Not applicable in this context
- **🚫 DISABLED** - Intentionally excluded by configuration
- **⚠️ PARTIAL** - Partially working, needs attention
- **❌ FAIL** - Something went wrong

### Example Output
```
================================================================
SETUP REPORT
================================================================
STEP                                     STATUS
----------------------------------------------------------------
GitHub CLI Installation                  ✅ VERIFIED
SSH Key Generation                       ✅ VERIFIED
SSH Key GitHub Integration               ✅ VERIFIED
Cursor Agent Installation                ✅ VERIFIED
Gemini CLI Installation                  ✅ VERIFIED
Python Installation                      ✅ VERIFIED
Node.js Installation                     ✅ VERIFIED
Environment File Detection               ✅ VERIFIED
Secrets Backup Validation                ⏭️ SKIP
----------------------------------------------------------------
SUMMARY: 8 verified, 1 skipped
================================================================
```

## 🔧 Troubleshooting

### SSH Key Issues
```bash
# Check SSH agent status
ssh-add -l

# Add your key manually
ssh-add ~/.ssh/id_ed25519

# Test GitHub connection
ssh -T git@github.com
```

### Node.js Issues
```bash
# Reload shell configuration
source ~/.bashrc

# Use specific Node.js version
nvm use 20

# Check Node.js installation
node --version
```

### Environment Variables Not Loading
```bash
# Check if .env file exists
ls -la ~/.env

# Manually load for current session
source ~/.env

# Check if variables are loaded
echo $GEMINI_API_KEY
```

### Google Cloud CLI Issues
```bash
# Check authentication
gcloud auth list

# Re-authenticate
gcloud auth login

# Check project configuration
gcloud config get-value project
```

### Secrets Backup Issues
```bash
# Check if PROJECT_ID is set
grep PROJECT_ID ~/.config

# Set PROJECT_ID in .config
echo "PROJECT_ID=your-project-id" >> ~/.config

# Test backup
make backup
```

## 🎯 Prerequisites

- **ChromeOS** with Linux development environment enabled (Crostini)
- **Internet connection** for downloading tools and packages
- **GitHub account** for SSH key setup and authentication
- **Google Cloud account** (optional, for secrets backup)

## 🔮 Future Enhancements

### Advanced Features
- **Docker Support** - Install and configure Docker for containerized development
- **Additional CLIs** - AWS CLI, Azure CLI, kubectl, terraform
- **Database Tools** - PostgreSQL, MySQL, MongoDB clients
- **Code Quality** - ESLint, Prettier, Black, isort
- **IDE Integration** - VS Code, IntelliJ, Vim/Neovim configurations

### Environment Management
- **Profile Switching** - Different configurations for different projects
- **Dotfiles Management** - Automated management of shell configurations
- **Health Checks** - Automated verification that all tools are working
- **Update Notifications** - Notify when new versions are available

### Security Enhancements
- **Secrets Validation** - Verify that required API keys are present and valid
- **Multiple Secrets Sources** - Support for loading from multiple files
- **Encryption Options** - Additional encryption methods for sensitive data

## 🤝 Contributing

This is a personal development environment setup. If you find issues or want to suggest improvements:

1. **Create an issue** - Report bugs or request features
2. **Fork and submit PR** - Contribute code improvements
3. **Share feedback** - Let me know what works well or needs improvement

## 📄 License

This project is for personal use. Feel free to adapt it for your own development environment setup.

---

**Note**: This script is specifically designed for ChromeOS development environments. While it may work on other Linux distributions, it's optimized for Crostini/gLinux VMs running on ChromeOS.