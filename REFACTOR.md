# Refactor Analysis: Consolidating User File Commands

## Current State

Three overlapping mechanisms for managing per-repo user files:

| Command | What it syncs | Destination | File selection |
|---------|---------------|-------------|----------------|
| `devws local push/pull` | Gitignored files | GCS `repos/{owner}/{repo}/` | `.ws-sync` file |
| `devws repo user-archive` | Gitignored files + git bundle | Local zip (or Google Drive) | `# user-files` in `.gitignore` |
| `devws bundle` (planned) | Git bundle only | GCS `bundles/` | Entire repo |

### Problems

1. **Two file selection mechanisms**: `.ws-sync` vs `# user-files` section in `.gitignore`
2. **Scattered namespace**: `local` vs `repo` vs planned `bundle`
3. **Duplicate concepts**: All are "user files tied to a repo"
4. **Confusing naming**: `devws local` sounds like "local operations" but actually syncs to cloud
5. **Unnecessary zipping**: Current `user-archive` creates zip files, but GCS sync should use direct file copies like other commands

## Proposed Consolidation

### Namespace: `devws repo`

All commands require a git repo context and tie to the repo identity. Using `repo` makes this clear.

```
devws repo
├── push [--repo=bundle|snapshot|omit]  # Push user files (+ optional versioned files) to GCS
├── pull [--repo=bundle|snapshot|omit]  # Pull user files (+ optional versioned files) from GCS
├── status                              # Show sync status
├── init                                # Initialize # user-files section
└── archive [--target-folder .]         # Create portable zip for offline storage
```

### Single File Selection: `# user-files` in `.gitignore`

Deprecate `.ws-sync` in favor of the `# user-files` section in `.gitignore`.

**Rationale:**
- Single source of truth
- Files are already gitignored (required for this use case)
- No extra file to manage
- Already implemented for `user-archive`

**Format:**
```gitignore
# ... other gitignore patterns ...

# user-files
config.yaml
user-*.*
.env
```

Section ends at next blank line or EOF.

### Versioned Files: `--repo` Option

The `--repo` option controls how versioned files are handled:

| Option | Behavior |
|--------|----------|
| (not specified) | **Default.** Only sync user files. No versioned files. Same as current `devws local push`. |
| `--repo=bundle` | Also include `repo.bundle` (git bundle with full history) |
| `--repo=snapshot` | Also include current working tree files (no history, flat copy) |

**Rationale:**
- Default (no flag): Routine config sync doesn't need repo - it's already on the remote. This matches current `devws local push` behavior.
- `--repo=bundle`: Full disaster recovery, useful for local-only repos or archival
- `--repo=snapshot`: Lightweight copy of current state, useful when you just want the files without git history

### GCS Path Structure (No Zips)

Files are synced directly to GCS as individual files (consistent with existing `devws local` behavior):

```
gs://{bucket}/
└── repos/
    └── {owner}/{repo}/
        ├── REPO-SYNC.md              # Always included: remote URLs, commit, branch, restore instructions
        ├── user-files/               # User files subfolder
        │   ├── config.yaml
        │   ├── .env
        │   └── input.json
        ├── repo.bundle               # Only when --repo=bundle
        └── snapshot/                 # Only when --repo=snapshot
            ├── src/
            │   └── main.py
            ├── README.md
            └── ...
```

**Key points:**
- No `.zip` files - direct gsutil cp like other devws commands
- User files go in `user-files/` subfolder for clean separation
- `REPO-SYNC.md` always included at root with:
  - Remote URLs (for re-attaching after restore)
  - Current branch and commit hash
  - Restore instructions
- Staging happens in `/tmp/*`, then gsutil copies to GCS

### Local Archive (Portable Zip)

`devws repo archive` remains for **portable offline storage** (USB, Google Drive manual upload, etc.):

```bash
devws repo archive --target-folder .                    # Zip with bundle (default for archive)
devws repo archive --target-folder . --repo=snapshot    # Zip with snapshot instead of bundle
devws repo archive --target-folder . --no-repo          # Zip with user files only
```

**Note:** For `archive`, the default includes the bundle (unlike `push/pull` which default to user files only). This is because archives are typically for disaster recovery or offline storage where having the repo is important.

This is the only command that creates a `.zip` file.

### Configuration

Use existing `~/.config/devws/config.yaml` for GCS bucket/profile settings. No per-repo `user-backup.yaml` needed.

## Migration Path

### Phase 1: Add `devws repo` commands
- Implement `devws repo push/pull/status/init` using `# user-files` section
- Keep `devws local` working for backwards compatibility
- Add deprecation warning to `devws local` commands

### Phase 2: Update `devws repo user-archive`
- Rename to `devws repo archive`
- Remove Google Drive code (half-baked, revisit later)
- Remove `user-backup.yaml` support
- Add `--repo=bundle|snapshot` and `--no-repo` options

### Phase 3: Deprecate `devws local`
- Remove `devws local` commands
- Update documentation
- Remove `.ws-sync` parsing code

## Command Comparison: Before and After

### Before
```bash
# Sync user files
devws local init          # Creates .ws-sync
devws local push          # Pushes files in .ws-sync to GCS
devws local pull          # Pulls files in .ws-sync from GCS

# Archive with bundle
devws repo user-archive --target-folder .

# Bundle only (planned, not implemented)
devws bundle push
devws bundle pull
```

### After
```bash
# Sync user files only (default, same as current devws local)
devws repo init           # Adds # user-files section to .gitignore
devws repo push           # Pushes user-files/ to GCS
devws repo pull           # Pulls user-files/ from GCS

# Include versioned files in sync
devws repo push --repo=bundle      # Also push repo.bundle
devws repo push --repo=snapshot    # Also push snapshot/ of working tree

# Portable archive (bundle included by default)
devws repo archive --target-folder .
devws repo archive --target-folder . --repo=snapshot  # Snapshot instead of bundle
devws repo archive --target-folder . --no-repo        # User files only
```

## Restore Workflows

### Scenario 1: Repo exists on remote (typical case)
```bash
git clone <remote-url>
cd <repo>
devws repo pull           # Pulls user-files/ from GCS
```

### Scenario 2: Restore with bundle (remote gone or local-only repo)
```bash
# If you pushed with --repo=bundle:
devws repo pull --repo=bundle
# This pulls:
#   - REPO-SYNC.md (instructions)
#   - user-files/ (your config)
#   - repo.bundle (full repo)

# Then restore from bundle:
git clone repo.bundle <repo-name>
cd <repo-name>
mv ../user-files/* .
git remote add origin <url-from-REPO-SYNC.md>  # If remote still exists
```

### Scenario 3: Restore with snapshot (no git history needed)
```bash
devws repo pull --repo=snapshot
# This pulls:
#   - REPO-SYNC.md (instructions)
#   - user-files/ (your config)
#   - snapshot/ (working tree files)

# Snapshot is ready to use as-is, or init as new repo:
cd snapshot
git init
mv ../user-files/* .
```

### Scenario 4: Restore from portable archive
```bash
unzip repo-name_2025-12-02_1234.zip
cd <extracted-folder>
# Follow instructions in REPO-ARCHIVE.md
git clone repo.bundle <repo-name>
cd <repo-name>
cp ../user-files/* .
```

The `REPO-SYNC.md` (for GCS) and `REPO-ARCHIVE.md` (for zip) contain:
- Original remote URLs with `git remote add` commands
- Branch and commit hash at sync/archive time
- `git checkout <commit>` command to restore exact state
- List of user files and where they belong
- **Both manual restore instructions (gsutil/git commands) and devws commands**

This ensures restore is possible even without devws installed.

## Future Enhancements

### Google Drive Archive Upload

A future enhancement could add `--target=drive` to `devws repo archive` for uploading the zip directly to Google Drive:

```bash
devws repo archive --target=drive                    # Upload to configured Drive folder
devws repo archive --target=drive --folder-id=XXX   # Upload to specific folder
```

This would provide a "consumer durability" backup option separate from GCS, useful for:
- Long-term archival independent of GCP project lifecycle
- Sharing complete project state with others
- Personal backup to a trusted, permanent location
- Transferring ownership to another Google account (useful for sensitive projects or client handoffs)

**Implementation notes:**
- Requires OAuth with `drive.file` scope (already added to gwsa)
- Could use existing `upload_to_google_drive()` function from current `repo_commands.py`
- Should be added to TODO.md as a future enhancement once core refactor is complete

## Open Questions

1. **What about existing `.ws-sync` files?**
   - Option A: Auto-migrate patterns to `# user-files` section on first run
   - Option B: Support both during transition, warn about `.ws-sync` deprecation

2. **Should `devws repo init` create the `# user-files` section or just validate it exists?**
   - Probably: Check if section exists, if not, prompt to add it with suggested patterns

3. **Archive naming convention?**
   - Current: `{repo-name}_{YYYY-MM-DD_HHMM}.zip`
   - Keep as-is, or add customization option?

4. **Should `status` show bundle state in GCS?**
   - Probably yes: Show whether bundle exists and its timestamp

## Files to Modify

- `devws_cli/repo_commands.py` - Expand with push/pull/status/init
- `devws_cli/local_commands.py` - Add deprecation warnings, eventually remove
- `devws_cli/cli.py` - Update command registration
- `README.md` - Update documentation
- `ALTERNATIVES.md` - Already references the gap this fills

## Benefits of Consolidation

1. **Simpler mental model**: One namespace (`repo`) for all repo-tied operations
2. **Single file list**: `# user-files` in `.gitignore`, no extra `.ws-sync`
3. **Clear bundle semantics**: Opt-in for sync, default for archive
4. **Cleaner codebase**: Remove duplicate file-selection logic
5. **Better naming**: `devws repo` clearly indicates git context required
