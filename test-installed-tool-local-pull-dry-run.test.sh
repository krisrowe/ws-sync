#!/bin/bash

set -e

echo "=== Testing Installed devws Tool - Local Pull Dry Run ==="

# Step 1: Uninstall existing devws if present
echo "Step 1: Uninstalling existing devws (if present)..."
pipx uninstall devws 2>/dev/null || echo "No existing devws installation found"

# Step 2: Install latest version from local repository
echo "Step 2: Installing devws from local repository..."
pipx install --force /home/user/ws-sync

# Step 3: Verify installation
echo "Step 3: Verifying installation..."
which devws
devws --version || devws --help | head -5

# Step 4: Change to zscaler directory
echo "Step 4: Changing to ~/test-project directory..."
cd ~/test-project

# Step 5: Run devws local pull --dry-run
echo "Step 5: Running 'devws local pull --dry-run'..."
echo "=========================================="
devws local pull --dry-run
echo "=========================================="

echo ""
echo "=== Test Complete ==="
echo "Review the output above to verify dry-run behavior"
