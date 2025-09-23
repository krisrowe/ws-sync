# ChromeOS Development Environment Setup Makefile

.PHONY: help install setup backup restore clean

# Default target
help:
	@echo "ChromeOS Development Environment Setup"
	@echo ""
	@echo "Available targets:"
	@echo "  make setup     - Run the full setup process"
	@echo "  make backup    - Backup ~/.env to Google Secrets Manager"
	@echo "  make restore   - Restore ~/.env from Google Secrets Manager"
	@echo "  make clean     - Clean up temporary files"
	@echo "  make help      - Show this help message"
	@echo ""
	@echo "Prerequisites:"
	@echo "  - Git repository cloned"
	@echo "  - For backup/restore: Google Cloud CLI authenticated"

# Main setup target
setup: setup.sh
	@echo "Running ChromeOS development environment setup..."
	@chmod +x setup.sh
	@./setup.sh

# Secrets management targets
backup: secrets.sh
	@echo "Backing up environment to Google Secrets Manager..."
	@chmod +x secrets.sh
	@./secrets.sh backup

restore: secrets.sh
	@echo "Restoring environment from Google Secrets Manager..."
	@chmod +x secrets.sh
	@./secrets.sh restore

# Cleanup target
clean:
	@echo "Cleaning up temporary files..."
	@find . -name "*.backup.*" -type f -delete 2>/dev/null || true
	@echo "Cleanup complete"

# Ensure scripts are executable
setup.sh:
	@chmod +x setup.sh

secrets.sh:
	@chmod +x secrets.sh
