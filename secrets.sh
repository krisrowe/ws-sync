#!/bin/bash

# ==============================================================================
# .env File Backup/Restore Script
#
# This script backs up your ~/.env file to Google Secrets Manager
# and restores it back to your local environment.
#
# Usage:
#   ./secrets.sh backup    - Backup ~/.env to Google Secrets Manager
#   ./secrets.sh restore   - Restore from Google Secrets Manager to ~/.env
# ==============================================================================

# Configuration
ENV_FILE="$HOME/.env"
SECRET_NAME="dotenv-backup"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        log_error "Google Cloud CLI not found. Please install it first."
        echo "Run: ./setup.sh to install gcloud CLI"
        exit 1
    fi
}

check_auth() {
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_warning "Not authenticated with Google Cloud."
        echo "Please authenticate with Google Cloud to continue..."
        if gcloud auth login; then
            log_success "Successfully authenticated with Google Cloud"
        else
            log_error "Failed to authenticate with Google Cloud"
            exit 1
        fi
    fi
}

get_project() {
    local project=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$project" ]; then
        log_error "No GCP project configured."
        echo "Run: gcloud config set project YOUR_PROJECT_ID"
        exit 1
    fi
    echo "$project"
}

backup_env() {
    local project=$(get_project)
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found at $ENV_FILE"
        echo "Create your environment file first or run ./setup.sh"
        exit 1
    fi
    
    log_info "Backing up $ENV_FILE to Google Secrets Manager..."
    log_info "Project: $project"
    log_info "Secret name: $SECRET_NAME"
    
    # Enable Secret Manager API if not already enabled
    log_info "Ensuring Secret Manager API is enabled..."
    if gcloud services enable secretmanager.googleapis.com --project="$project" &>/dev/null; then
        log_success "Secret Manager API enabled"
    else
        log_warning "Secret Manager API may already be enabled"
    fi
    
    # Create or update the secret
    if gcloud secrets describe "$SECRET_NAME" --project="$project" &>/dev/null; then
        log_info "Secret $SECRET_NAME already exists. Updating..."
        if gcloud secrets versions add "$SECRET_NAME" --data-file="$ENV_FILE" --project="$project" &>/dev/null; then
            log_success "Environment file backed up successfully!"
        else
            log_error "Failed to backup environment file"
            exit 1
        fi
    else
        log_info "Creating new secret $SECRET_NAME..."
        if gcloud secrets create "$SECRET_NAME" --data-file="$ENV_FILE" --project="$project" &>/dev/null; then
            log_success "Environment file backed up successfully!"
        else
            log_error "Failed to create secret"
            exit 1
        fi
    fi
    
    # Show backup info
    local version=$(gcloud secrets versions list "$SECRET_NAME" --project="$project" --format="value(name)" --limit=1 2>/dev/null)
    if [ -n "$version" ]; then
        log_info "Latest version: $version"
    fi
}

restore_env() {
    local project=$(get_project)
    
    log_info "Restoring environment file from Google Secrets Manager..."
    log_info "Project: $project"
    log_info "Secret name: $SECRET_NAME"
    
    # Check if secret exists
    if ! gcloud secrets describe "$SECRET_NAME" --project="$project" &>/dev/null; then
        log_error "Secret $SECRET_NAME not found in project $project"
        echo "Run './secrets.sh backup' first to create the secret"
        exit 1
    fi
    
    # Backup current .env file if it exists
    if [ -f "$ENV_FILE" ]; then
        local backup_file="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Backing up current .env file to $backup_file"
        cp "$ENV_FILE" "$backup_file"
    fi
    
    # Restore from Secret Manager
    if gcloud secrets versions access latest --secret="$SECRET_NAME" --project="$project" > "$ENV_FILE"; then
        log_success "Environment file restored successfully!"
        log_info "Restored to: $ENV_FILE"
        
        # Set proper permissions
        chmod 600 "$ENV_FILE"
        log_info "Set secure permissions on $ENV_FILE"
    else
        log_error "Failed to restore environment file"
        exit 1
    fi
}

show_help() {
    echo ".env File Backup/Restore Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  backup    Backup ~/.env to Google Secrets Manager"
    echo "  restore   Restore from Google Secrets Manager to ~/.env"
    echo ""
    echo "Prerequisites:"
    echo "  - Google Cloud CLI installed and authenticated"
    echo "  - GCP project configured"
    echo "  - Secret Manager API enabled"
    echo ""
    echo "Examples:"
    echo "  $0 backup          # Backup current ~/.env file"
    echo "  $0 restore         # Restore ~/.env from cloud"
}

# Main script logic
main() {
    case "${1:-help}" in
        "backup")
            check_gcloud
            check_auth
            backup_env
            ;;
        "restore")
            check_gcloud
            check_auth
            restore_env
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
