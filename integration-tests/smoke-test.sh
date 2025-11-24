#!/bin/bash
# Smoke test for devws CLI before commits
# Usage: ./smoke-test.sh [other-repo-path]
#
# This script validates:
# 1. devws setup --dry-run shows all components as VERIFIED
# 2. devws local commands work in a real repository with .ws-sync

set -e

OTHER_REPO_PATH="${1:-}"

echo "=== devws Smoke Test ==="
echo ""

# Test 1: devws setup --dry-run
echo "1. Running devws setup --dry-run..."
SETUP_OUTPUT=$(devws setup --dry-run 2>&1)

# Check that all installed components show VERIFIED
if echo "$SETUP_OUTPUT" | grep -q "VERIFIED"; then
    echo "✅ Found VERIFIED components"
else
    echo "❌ No VERIFIED components found"
    echo "$SETUP_OUTPUT"
    exit 1
fi

# Check for any FAILED components
if echo "$SETUP_OUTPUT" | grep -q "FAIL"; then
    echo "❌ Found FAILED components"
    echo "$SETUP_OUTPUT"
    exit 1
fi

echo "✅ devws setup --dry-run passed"
echo ""

# Test 2: devws local commands (if other repo path provided)
if [ -n "$OTHER_REPO_PATH" ]; then
    echo "2. Testing devws local commands in $OTHER_REPO_PATH..."
    
    # Validate other repo path
    if [ ! -d "$OTHER_REPO_PATH" ]; then
        echo "❌ Error: Directory does not exist: $OTHER_REPO_PATH"
        exit 1
    fi
    
    if [ ! -f "$OTHER_REPO_PATH/.ws-sync" ]; then
        echo "❌ Error: No .ws-sync file found in: $OTHER_REPO_PATH"
        echo "   This doesn't appear to be a repository using devws local"
        exit 1
    fi
    
    echo "✅ Valid repository with .ws-sync found"
    
    # Change to other repo
    cd "$OTHER_REPO_PATH"
    
    # Test devws local push
    echo "  Running devws local push..."
    if devws local push > /tmp/smoke-push.log 2>&1; then
        echo "  ✅ devws local push succeeded"
    else
        echo "  ❌ devws local push failed"
        cat /tmp/smoke-push.log
        exit 1
    fi
    
    # Test devws local pull --dry-run
    echo "  Running devws local pull --dry-run..."
    if devws local pull --dry-run > /tmp/smoke-pull-dry.log 2>&1; then
        echo "  ✅ devws local pull --dry-run succeeded"
    else
        echo "  ❌ devws local pull --dry-run failed"
        cat /tmp/smoke-pull-dry.log
        exit 1
    fi
    
    echo "✅ devws local commands passed"
else
    echo "2. Skipping devws local tests (no other-repo-path provided)"
    echo "   Usage: ./smoke-test.sh ~/path/to/other-repo"
fi

echo ""
echo "=== Smoke Test Complete ✅ ==="
echo "All tests passed. Safe to commit."
