# GEMINI.md - Development Guidelines for AI Assistants

This document provides context and guidelines for AI assistants (like Gemini) working on this repository.

## Project Overview

This is the `ws-sync` repository, which provides a Python CLI tool called `devws` for managing ChromeOS development workstation setup and project-specific configuration synchronization.

## Key Commands

- `devws setup` - Sets up the development environment (idempotent)
- `devws local pull/push` - Synchronizes project-specific files via GCS
- `devws local status` - Shows sync status of managed files
- `devws env backup/restore` - Manages global environment files via Google Secrets Manager

## Testing and Validation

### Temporary Validation Scripts

Use `*.temp.sh` for ad-hoc validation scripts, particularly when testing the CLI in other working directories outside this repo (e.g., `~/my-other-repo` when testing `devws local push --dry-run` with a repo that uses this CLI for local-only files management).

**Important:** Do NOT commit `*.temp.sh` files. They are for temporary validation only.

### Smoke Test Before Commits

Before committing changes, run the smoke test to ensure everything works:

```bash
./integration-tests/smoke-test.sh ~/path/to/other-repo
```

The smoke test performs:
1. **devws setup --dry-run** - Confirms all components show VERIFIED (already installed)
2. **devws local commands** - Tests push and pull --dry-run in a real repository with `.ws-sync`

#### Smoke Test Script

Location: `./integration-tests/smoke-test.sh`

Usage:
```bash
./integration-tests/smoke-test.sh [other-repo-path]
```

The script:
- Validates that a valid other repo path was provided (checks for repo existence and `.ws-sync` file)
- Changes to that directory
- Runs `devws local push`
- Runs `devws local pull --dry-run`
- Reports success/failure

### Integration Tests

Full integration tests are located in `./integration-tests/`. Key test cases:
- `test-case-1.sh` - Basic setup and configuration
- `test-case-4.sh` - Local file synchronization
- `test-case-10.sh` - Dry-run validation

## Code Organization

- `devws_cli/` - Main Python package
  - `cli.py` - CLI entry point
  - `setup_commands.py` - Setup command logic
  - `local_commands.py` - Local sync commands
  - `components/` - Individual setup components (Python, Node.js, GitHub, etc.)
  - `utils.py` - Shared utilities
- `integration-tests/` - Integration test scripts
- `tests/` - Unit tests (pytest)

## Component Status Logic

Components use a consistent status reporting system:
- **VERIFIED** - Already installed/configured
- **READY** - Missing, would install (dry-run mode)
- **COMPLETED** - Successfully installed/configured
- **FAILED** - Installation/configuration failed

## Configuration

- Global config: `~/.config/devws/config.yaml`
- Default config template: `devws_cli/config.default.yaml`
- Project-specific: `.ws-sync` file in repository root

## Common Patterns

### Adding a New Component

1. Create `devws_cli/components/your_component.py`
2. Implement `setup(config, dry_run=False)` function
3. Add component to `config.default.yaml`
4. Component should call `_log_step()` with appropriate status

### Testing Changes

1. Run `devws setup --dry-run` to verify no regressions
2. Run smoke test with a real repository
3. Run integration tests: `./integration-tests/test-case-*.sh`
4. Run unit tests: `pytest tests/`

## Future Enhancements

See `TODO.md` for planned improvements, including:
- Categorized setup output with centralized reporting
- `devws user-home` command for managing non-repo-specific files
- Enhanced sync status validation
