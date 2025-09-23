#!/bin/bash

# ==============================================================================
# ChromeOS Development Environment Setup Script (Idempotent Version)
#
# This script is a resilient "bootstrap" for a new Crostini/gLinux VM.
# It can be run repeatedly without issues to:
# - Set up a new environment from scratch.
# - Re-run and extend the setup with new tools or configurations.
# - Repair a broken or partially configured environment.
#
# The script checks for the existence of each component before installing or
# configuring it.
#
# Prerequisites:
# 1. Clone this repository: git clone https://github.com/github-user/ws-sync.git
# 2. Navigate to the repository: cd ws-sync
# 3. Run this script: ./setup.sh
# ==============================================================================

# --- Configuration ---
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_KEY_FILE="$HOME/.ssh/id_ed25519"
ENV_FILE="$HOME/.env"

# Load configuration from .config file
CONFIG_EXAMPLE_FILE="$REPO_DIR/.config.example"
CONFIG_FILE="$REPO_DIR/.config"
ENV_FILE="$HOME/.env"

# Create .config from .config.example if it doesn't exist
if [ ! -f "$CONFIG_FILE" ] && [ -f "$CONFIG_EXAMPLE_FILE" ]; then
    echo "Creating .config file from .config.example..."
    cp "$CONFIG_EXAMPLE_FILE" "$CONFIG_FILE"
    echo "Please edit $CONFIG_FILE to customize your settings."
fi

# Load configuration
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
    echo "Configuration loaded from $CONFIG_FILE"
else
    echo "Warning: No .config file found. Using default settings..."
    # Default values
    ENABLE_GITHUB_SETUP=true
    ENABLE_GOOGLE_CLOUD_CLI=true
    ENABLE_PYTHON=true
    PYTHON_MIN_VERSION="3.9"
    ENABLE_NODEJS=true
    NODEJS_MIN_VERSION="20"
    ENABLE_CURSOR_AGENT=true
    ENABLE_GEMINI_CLI=true
    ENABLE_ENV_SETUP=true
fi

# Status tracking
declare -A STEP_STATUS
STEP_COUNT=0

# Helper function to validate secrets backup
validate_secrets_backup() {
    # Check if PROJECT_ID is set in config
    if [ -n "$PROJECT_ID" ]; then
        # Use PROJECT_ID from config
        local project="$PROJECT_ID"
    else
        # Fall back to gcloud config
        local project=$(gcloud config get-value project 2>/dev/null)
    fi
    
    # Only SKIP if no GCP project is specified
    if [ -z "$project" ]; then
        log_step "Secrets Backup Validation" "SKIP"
        echo "  → Set PROJECT_ID in .config to enable secrets backup validation"
        return 0
    fi
    
    # If GCP project is specified, we expect validation to work
    if [ ! -f "$ENV_FILE" ]; then
        log_step "Secrets Backup Validation" "FAIL"
        return 1
    fi
    
    # Check if gcloud is available and authenticated
    if ! command -v gcloud &> /dev/null; then
        log_step "Secrets Backup Validation" "FAIL"
        return 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_step "Secrets Backup Validation" "FAIL"
        return 1
    fi
    
    # Check if secret exists in Google Secrets Manager
    if ! gcloud secrets describe dotenv-backup --project="$project" &>/dev/null; then
        log_step "Secrets Backup Validation" "FAIL"
        return 1
    fi
    
    # Compare local file with stored secret
    local local_hash=$(sha256sum "$ENV_FILE" | cut -d' ' -f1)
    local stored_content=$(gcloud secrets versions access latest --secret="dotenv-backup" --project="$project" 2>/dev/null)
    
    if [ -z "$stored_content" ]; then
        log_step "Secrets Backup Validation" "FAIL"
        return 1
    fi
    
    local stored_hash=$(echo "$stored_content" | sha256sum | cut -d' ' -f1)
    
    if [ "$local_hash" = "$stored_hash" ]; then
        log_step "Secrets Backup Validation" "PASS"
        return 0
    else
        log_step "Secrets Backup Validation" "PARTIAL"
        return 1
    fi
}

# Helper functions
log_step() {
    local step_name="$1"
    local status="$2"
    STEP_COUNT=$((STEP_COUNT + 1))
    STEP_STATUS["$step_name"]="$status"
    
    case "$status" in
        "PASS")
            echo "✅ $step_name - PASSED"
            ;;
        "COMPLETED")
            echo "✅ $step_name - COMPLETED (just finished)"
            ;;
        "VERIFIED")
            echo "✅ $step_name - VERIFIED (already done)"
            ;;
        "SKIP")
            echo "⏭️  $step_name - SKIPPED (not applicable)"
            ;;
        "DISABLED")
            echo "🚫 $step_name - DISABLED (configuration)"
            ;;
        "PARTIAL")
            echo "⚠️  $step_name - PARTIAL (needs attention)"
            ;;
        "FAIL")
            echo "❌ $step_name - FAILED"
            ;;
    esac
}

print_final_report() {
    echo ""
    echo "================================================================"
    echo "SETUP REPORT"
    echo "================================================================"
    printf "%-40s %s\n" "STEP" "STATUS"
    echo "----------------------------------------------------------------"
    
    for step in "${!STEP_STATUS[@]}"; do
        local status="${STEP_STATUS[$step]}"
        case "$status" in
        "PASS")
            printf "%-40s %s\n" "$step" "✅ PASS"
            ;;
        "COMPLETED")
            printf "%-40s %s\n" "$step" "✅ COMPLETED"
            ;;
        "VERIFIED")
            printf "%-40s %s\n" "$step" "✅ VERIFIED"
            ;;
        "SKIP")
            printf "%-40s %s\n" "$step" "⏭️  SKIP"
            ;;
        "DISABLED")
            printf "%-40s %s\n" "$step" "🚫 DISABLED"
            ;;
        "PARTIAL")
            printf "%-40s %s\n" "$step" "⚠️  PARTIAL"
            ;;
        "FAIL")
            printf "%-40s %s\n" "$step" "❌ FAIL"
            ;;
        esac
    done
    
    local completed_count=$(printf '%s\n' "${STEP_STATUS[@]}" | grep -c "COMPLETED")
    local verified_count=$(printf '%s\n' "${STEP_STATUS[@]}" | grep -c "VERIFIED")
    local skip_count=$(printf '%s\n' "${STEP_STATUS[@]}" | grep -c "SKIP")
    local disabled_count=$(printf '%s\n' "${STEP_STATUS[@]}" | grep -c "DISABLED")
    local partial_count=$(printf '%s\n' "${STEP_STATUS[@]}" | grep -c "PARTIAL")
    local fail_count=$(printf '%s\n' "${STEP_STATUS[@]}" | grep -c "FAIL")
    
    echo "----------------------------------------------------------------"
    # Build summary with only non-zero counts
    local summary_parts=()
    [ $completed_count -gt 0 ] && summary_parts+=("$completed_count completed")
    [ $verified_count -gt 0 ] && summary_parts+=("$verified_count verified")
    [ $skip_count -gt 0 ] && summary_parts+=("$skip_count skipped")
    [ $disabled_count -gt 0 ] && summary_parts+=("$disabled_count disabled")
    [ $partial_count -gt 0 ] && summary_parts+=("$partial_count partial")
    [ $fail_count -gt 0 ] && summary_parts+=("$fail_count failed")
    
    if [ ${#summary_parts[@]} -gt 0 ]; then
        echo "SUMMARY: $(IFS=', '; echo "${summary_parts[*]}")"
    else
        echo "SUMMARY: No steps processed"
    fi
    echo "================================================================"
    
    # Action items for fails and partials
    local has_actions=false
    for step in "${!STEP_STATUS[@]}"; do
        local status="${STEP_STATUS[$step]}"
        if [ "$status" = "FAIL" ] || [ "$status" = "PARTIAL" ]; then
            if [ "$has_actions" = false ]; then
                echo ""
                echo "ACTION ITEMS:"
                echo "----------------------------------------------------------------"
                has_actions=true
            fi
            case "$step" in
                "GitHub CLI Installation")
                    echo "• Install GitHub CLI manually: https://cli.github.com/"
                    ;;
                "Google Cloud CLI Installation")
                    echo "• Install Google Cloud CLI manually: https://cloud.google.com/sdk/docs/install"
                    ;;
                "Cursor Agent Installation")
                    echo "• Fix npm permissions or install cursor-agent manually"
                    ;;
                "Gemini CLI Installation")
                    echo "• Fix npm permissions or install @google/gemini-cli manually"
                    ;;
                "Python Installation")
                    echo "• Install Python $PYTHON_MIN_VERSION or later manually"
                    ;;
                "Node.js Installation")
                    echo "• Install Node.js $NODEJS_MIN_VERSION or later manually"
                    ;;
                "Environment File Detection")
                    echo "• Create ~/.env file with your API keys"
                    ;;
                "Secrets Backup Validation")
                    if [ "$status" = "SKIP" ]; then
                        echo "• Set PROJECT_ID in .config to enable secrets backup validation"
                    else
                        echo "• Run 'make backup' to backup your environment to Google Secrets Manager"
                    fi
                    ;;
                "Current Session Environment Loading")
                    echo "• Check ~/.env file syntax and permissions"
                    ;;
            esac
        fi
    done
    
    if [ "$has_actions" = true ]; then
        echo "----------------------------------------------------------------"
    fi
}

echo "================================================================"
echo "Starting ChromeOS Development Environment Setup"
echo "Repository: $REPO_DIR"
echo "----------------------------------------------------------------"

# --- Step 1: GitHub Setup (CLI + SSH) ---
if [ "$ENABLE_GITHUB_SETUP" = "true" ]; then
    echo "Step 1: GitHub Setup (CLI + SSH)"
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI not found. Installing gh cli..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if brew install gh; then
            log_step "GitHub CLI Installation" "PASS"
        else
            log_step "GitHub CLI Installation" "FAIL"
            echo "Please install GitHub CLI manually before proceeding."
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if sudo apt-get update && sudo apt-get install gh -y; then
            log_step "GitHub CLI Installation" "PASS"
        else
            log_step "GitHub CLI Installation" "FAIL"
            echo "Please install GitHub CLI manually before proceeding."
            exit 1
        fi
    else
        log_step "GitHub CLI Installation" "FAIL"
        echo "Please install GitHub CLI manually before proceeding."
        exit 1
    fi
else
    echo "GitHub CLI is already installed."
    log_step "GitHub CLI Installation" "VERIFIED"
fi

if ! gh auth status &> /dev/null; then
    echo "You are not authenticated with GitHub. Please log in now."
    if gh auth login; then
        log_step "GitHub CLI Authentication" "PASS"
    else
        log_step "GitHub CLI Authentication" "FAIL"
        exit 1
    fi
else
    echo "GitHub CLI is authenticated."
    log_step "GitHub CLI Authentication" "VERIFIED"
fi
echo "----------------------------------------------------------------"
fi

# --- Step 2: Install gcloud CLI ---
echo "Step 2: Google Cloud CLI Installation"
if ! command -v gcloud &> /dev/null; then
    echo "Google Cloud CLI not found. Installing gcloud cli..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if brew install --cask google-cloud-sdk; then
            log_step "Google Cloud CLI Installation" "PASS"
        else
            log_step "Google Cloud CLI Installation" "FAIL"
            echo "Please install Google Cloud CLI manually before proceeding."
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if sudo apt-get update && sudo apt-get install google-cloud-cli -y; then
            log_step "Google Cloud CLI Installation" "PASS"
        else
            log_step "Google Cloud CLI Installation" "FAIL"
            echo "Please install Google Cloud CLI manually before proceeding."
            exit 1
        fi
    else
        log_step "Google Cloud CLI Installation" "FAIL"
        echo "Please install Google Cloud CLI manually before proceeding."
        exit 1
    fi
else
    echo "Google Cloud CLI is already installed."
    log_step "Google Cloud CLI Installation" "VERIFIED"
fi
echo "----------------------------------------------------------------"

# --- Step 3: Set up SSH key using gh cli ---
if [ "$ENABLE_GITHUB_SETUP" = "true" ]; then
    echo "Step 3: SSH Key Setup and GitHub Integration"
if [ ! -f "$SSH_KEY_FILE" ]; then
    echo "No SSH key found. Generating a new Ed25519 key pair..."
    echo "Please enter your email to use as a comment for the key."
    read -p "Email: " EMAIL_COMMENT
    if ssh-keygen -t ed25519 -f "$SSH_KEY_FILE" -C "$EMAIL_COMMENT" -q -N ""; then
        log_step "SSH Key Generation" "PASS"
    else
        log_step "SSH Key Generation" "FAIL"
        exit 1
    fi
else
    echo "SSH key already exists at $SSH_KEY_FILE."
        log_step "SSH Key Generation" "VERIFIED"
fi

# Check if the key is already added to GitHub
# Extract just the key part (without the comment) for comparison
LOCAL_KEY_CONTENT=$(cat "${SSH_KEY_FILE}.pub" | awk '{print $1 " " $2}')
if ! gh ssh-key list | grep -q "$LOCAL_KEY_CONTENT"; then
    echo "Adding the public key to your GitHub account via gh cli..."
    if gh ssh-key add "${SSH_KEY_FILE}.pub" --title "$(uname -s) - $(whoami)@$(uname -n)" --type "authentication"; then
        echo "SSH key successfully added to GitHub."
        log_step "SSH Key GitHub Integration" "COMPLETED"
    else
        log_step "SSH Key GitHub Integration" "FAIL"
        exit 1
    fi
else
    echo "SSH key is already added to GitHub."
    log_step "SSH Key GitHub Integration" "VERIFIED"
fi

# Set up SSH agent to persist for the session and in .bashrc
if ! pgrep -u "$USER" ssh-agent > /dev/null; then
    eval "$(ssh-agent -s)" > /dev/null
    ssh-add "$SSH_KEY_FILE" > /dev/null
    echo "SSH agent is running and key has been added."
    log_step "SSH Agent Setup" "COMPLETED"
else
    echo "SSH agent is already running."
    log_step "SSH Agent Setup" "VERIFIED"
fi

# Add SSH agent startup to .bashrc if not already there
if ! grep -q "SSH-agent setup" "$HOME/.bashrc"; then
    cat << 'EOF' >> "$HOME/.bashrc"
# SSH-agent setup for GitHub access
if [ -f "$HOME/.ssh/id_ed25519" ] && ! pgrep -u "$USER" ssh-agent > /dev/null; then
    eval "$(ssh-agent -s)" > /dev/null
    ssh-add "$HOME/.ssh/id_ed25519" > /dev/null
fi
EOF
    echo "Added SSH agent startup to $HOME/.bashrc."
    log_step "SSH Agent Auto-start Configuration" "COMPLETED"
else
    echo "SSH agent setup already in $HOME/.bashrc."
    log_step "SSH Agent Auto-start Configuration" "VERIFIED"
fi
echo "----------------------------------------------------------------"
fi

# Navigate to repository directory (not user-configurable)
cd "$REPO_DIR" || { 
    echo "Failed to navigate to repository directory."
    exit 1
}

# --- Step 4: Install Cursor Agent ---
if [ "$ENABLE_CURSOR_AGENT" = "true" ]; then
    echo "Step 4: Cursor Agent Installation"
    
    if npm list -g cursor-agent &> /dev/null; then
        echo "Cursor agent is already installed."
        log_step "Cursor Agent Installation" "VERIFIED"
    else
        echo "Installing cursor-agent..."
        if sudo npm install -g cursor-agent; then
            echo "Cursor agent installation complete."
            log_step "Cursor Agent Installation" "COMPLETED"
        else
            echo "Failed to install cursor-agent."
            log_step "Cursor Agent Installation" "FAIL"
        fi
    fi
    echo "----------------------------------------------------------------"
fi

# --- Step 5: Install Gemini CLI ---
if [ "$ENABLE_GEMINI_CLI" = "true" ]; then
    echo "Step 5: Gemini CLI Installation"
    
    if command -v gemini &> /dev/null; then
        echo "Gemini CLI is already installed and accessible."
        log_step "Gemini CLI Installation" "VERIFIED"
        log_step "Gemini CLI Validation" "VERIFIED"
    else
        echo "Installing Gemini CLI..."
        if sudo npm install -g @google/gemini-cli; then
            echo "Gemini CLI installation complete."
            log_step "Gemini CLI Installation" "COMPLETED"
            
            # Validate Gemini CLI installation
            if command -v gemini &> /dev/null; then
                echo "Gemini CLI is accessible."
                log_step "Gemini CLI Validation" "COMPLETED"
            else
                echo "Gemini CLI installation failed - command not found."
                log_step "Gemini CLI Validation" "FAIL"
            fi
        else
            echo "Failed to install Gemini CLI."
            log_step "Gemini CLI Installation" "FAIL"
        fi
    fi
    echo "----------------------------------------------------------------"
fi

# --- Step 6: Python Installation ---
echo "Step 6: Python Installation"
if [ "$ENABLE_PYTHON" = "true" ]; then
    echo "Checking Python installation..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
        PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)
        REQUIRED_MAJOR=$(echo "$PYTHON_MIN_VERSION" | cut -d'.' -f1)
        REQUIRED_MINOR=$(echo "$PYTHON_MIN_VERSION" | cut -d'.' -f2)
        
        if [ "$PYTHON_MAJOR" -gt "$REQUIRED_MAJOR" ] || ([ "$PYTHON_MAJOR" -eq "$REQUIRED_MAJOR" ] && [ "$PYTHON_MINOR" -ge "$REQUIRED_MINOR" ]); then
            echo "Python $PYTHON_VERSION is already installed (meets minimum requirement $PYTHON_MIN_VERSION)."
            log_step "Python Installation" "VERIFIED"
        else
            echo "Python $PYTHON_VERSION is too old. Installing Python $PYTHON_MIN_VERSION or later..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                if brew install python@3.11; then
                    log_step "Python Installation" "PASS"
                else
                    log_step "Python Installation" "FAIL"
                fi
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                if sudo apt-get update && sudo apt-get install python3 python3-pip -y; then
                    log_step "Python Installation" "PASS"
                else
                    log_step "Python Installation" "FAIL"
                fi
            else
                echo "Unsupported OS for automatic Python installation."
                log_step "Python Installation" "FAIL"
            fi
        fi
    else
        echo "Python not found. Installing Python $PYTHON_MIN_VERSION or later..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if brew install python@3.11; then
                log_step "Python Installation" "PASS"
            else
                log_step "Python Installation" "FAIL"
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if sudo apt-get update && sudo apt-get install python3 python3-pip -y; then
                log_step "Python Installation" "PASS"
            else
                log_step "Python Installation" "FAIL"
            fi
        else
            echo "Unsupported OS for automatic Python installation."
            log_step "Python Installation" "FAIL"
        fi
    fi
    echo "----------------------------------------------------------------"
else
    echo "Python installation disabled in configuration."
    log_step "Python Installation" "DISABLED"
    echo "----------------------------------------------------------------"
fi

# --- Step 7: Check Node.js version and install if needed ---
echo "Step 7: Node.js Setup"
if [ "$ENABLE_NODEJS" = "true" ]; then
    if ! command -v node &> /dev/null; then
        echo "Node.js not found. Installing Node Version Manager (nvm)..."
        if curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash; then
            export NVM_DIR="$HOME/.nvm"
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            if nvm install "$NODEJS_MIN_VERSION" && nvm use "$NODEJS_MIN_VERSION"; then
                echo "Node.js version $NODEJS_MIN_VERSION installed and set as default."
                log_step "Node.js Installation" "PASS"
            else
                log_step "Node.js Installation" "FAIL"
            fi
        else
            log_step "Node.js Installation" "FAIL"
        fi
    else
        NODE_CURRENT_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
        if [[ "$NODE_CURRENT_VERSION" -lt "$NODEJS_MIN_VERSION" ]]; then
            echo "Node.js version is too old ($NODE_CURRENT_VERSION). Updating to version $NODEJS_MIN_VERSION."
            if nvm install "$NODEJS_MIN_VERSION" && nvm use "$NODEJS_MIN_VERSION"; then
                log_step "Node.js Update" "PASS"
            else
                log_step "Node.js Update" "FAIL"
            fi
        else
            echo "Node.js version is sufficient."
            log_step "Node.js Installation" "VERIFIED"
        fi
    fi
    echo "----------------------------------------------------------------"
else
    echo "Node.js installation disabled in configuration."
    log_step "Node.js Installation" "DISABLED"
    echo "----------------------------------------------------------------"
fi

# --- Step 8: Environment Configuration Setup ---
if [ "$ENABLE_ENV_SETUP" = "true" ]; then
    echo "Step 8: Environment Configuration Setup"
    echo "Setting up environment variable loading..."

    # Check if .env file exists
    if [ -f "$ENV_FILE" ]; then
        echo "Found environment file at $ENV_FILE"
        log_step "Environment File Detection" "VERIFIED"
    else
        echo "No environment file found at $ENV_FILE"
        echo "You can create one manually or use 'make backup' after setting up Google Cloud"
        log_step "Environment File Detection" "FAIL"
    fi

    # Add environment file loading to .bashrc if not already there
    if ! grep -q "Load environment file" "$HOME/.bashrc"; then
        cat << EOF >> "$HOME/.bashrc"

# Load environment file
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment from $ENV_FILE"
    source "$ENV_FILE"
fi
EOF
        echo "Added environment loading to $HOME/.bashrc."
        log_step "Shell Startup Integration" "COMPLETED"
    else
        echo "Environment loading already configured in $HOME/.bashrc."
        log_step "Shell Startup Integration" "VERIFIED"
    fi

# Note: .env file will be loaded by shell on startup via .bashrc configuration

# Check backup status (only if environment setup is enabled)
if [ "$ENABLE_ENV_SETUP" = "true" ]; then
    echo "Checking backup status..."
    validate_secrets_backup
fi

    echo ""
    echo "Environment file location: $ENV_FILE"
    echo "You can edit this file to add your API keys and configuration."
    echo "Use './secrets.sh' to backup/restore from Google Secrets Manager."
    echo "----------------------------------------------------------------"
fi

# --- Step 9: Final instructions and report ---
echo "Step 9: Finalizing Setup"

echo ""
echo "================================================================"
echo "SETUP COMPLETE!"
echo "================================================================"
echo ""
echo "Your ChromeOS development environment is now configured."
echo "Your SSH key is set up, tools are installed, and environment is ready."
echo ""
echo "Repository location: $REPO_DIR"
echo "Environment file: $ENV_FILE"
echo ""

# Print final status report
print_final_report

echo ""
# Check for issues and provide targeted guidance
has_issues=false

# Check for specific issues and provide targeted guidance
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "⚠️  ISSUES FOUND:"
    echo "----------------------------------------------------------------"
    echo "• Environment file missing: Create ~/.env file with your API keys"
    echo "• Run 'make backup' to backup your environment to Google Secrets Manager"
    has_issues=true
elif [ "${STEP_STATUS[Secrets Backup Validation]}" = "SKIP" ]; then
    echo ""
    echo "ℹ️  OPTIONAL ENHANCEMENTS:"
    echo "----------------------------------------------------------------"
    echo "• Secrets backup validation was SKIPPED (no PROJECT_ID configured)"
    echo "• To enable: Set PROJECT_ID in .config file"
    echo "• Then run 'make backup' to backup your environment to Google Secrets Manager"
    has_issues=true
elif [ "${STEP_STATUS[Secrets Backup Validation]}" = "PARTIAL" ]; then
    echo ""
    echo "⚠️  ISSUES FOUND:"
    echo "----------------------------------------------------------------"
    echo "• Environment backup is out of sync with Google Secrets Manager"
    echo "• Run 'make backup' to sync your environment with Google Secrets Manager"
    has_issues=true
elif [ "${STEP_STATUS[Secrets Backup Validation]}" = "PASS" ]; then
    echo ""
    echo "✅ ENVIRONMENT STATUS:"
    echo "----------------------------------------------------------------"
    echo "• Your environment is fully configured and backed up!"
    echo "• You can edit $ENV_FILE and run 'make backup' to update your backup"
    has_issues=true
fi

# If no specific issues, show success message
if [ "$has_issues" = false ]; then
    echo ""
    echo "✅ SETUP COMPLETE:"
    echo "----------------------------------------------------------------"
    echo "• Your development environment is ready!"
    echo "• Add API keys to $ENV_FILE as needed"
fi
echo ""
echo "================================================================"remove 