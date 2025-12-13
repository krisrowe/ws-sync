# ChromeOS Linux Terminal (Crostini) Integration

Guide to ChromeOS-specific features, automation, and limitations when using the Linux terminal.

## Architecture Overview

ChromeOS runs Linux in a VM called "Termina" which hosts containers (default: "penguin"). The integration uses:

- **9p filesystem** - Plan 9 protocol bridging Linux VM to ChromeOS
- **seneschal** - ChromeOS service controlling folder sharing
- **garcon** - Bridge service for Linux ↔ ChromeOS communication
- **sommelier** - Wayland compositor for GUI apps

## Filesystem Sharing

### Shared Folder Location
```
/mnt/chromeos/
├── fonts/           # ChromeOS fonts (auto-shared, read-only)
├── GoogleDrive/     # If shared
│   └── MyDrive/
└── MyFiles/         # If shared
    └── Downloads/
```

### How to Share Folders

**From ChromeOS Files app** (one-time, persists across reboots):
1. Open Files app
2. Right-click folder → "Share with Linux"
3. Folder appears under `/mnt/chromeos/`

**No CLI method exists** - security boundary prevents Linux from requesting filesystem access without explicit user action in ChromeOS UI.

### Google Drive Integration

Once shared, Google Drive is accessible at:
```
/mnt/chromeos/GoogleDrive/MyDrive/
```

**Sync behavior:**
- **Read/write supported** for regular files (PDF, TXT, JPG, etc.)
- Changes sync bidirectionally to Google Drive
- Appears to be synchronous (immediate write-through)

**Google native documents (Docs, Sheets, Slides):**
- Appear as small stub files (169 bytes): `.gdoc`, `.gsheet`, `.gslides`
- **Cannot be read or edited** from terminal (`cat` returns "Operation not supported")
- Can only be opened in browser
- To work with them programmatically, use Google APIs (gwsa, etc.)

### Example: Test Drive Write Access
```bash
echo "Test $(date)" > /mnt/chromeos/GoogleDrive/MyDrive/test.txt
cat /mnt/chromeos/GoogleDrive/MyDrive/test.txt
```

## Garcon Tools (Available from Linux)

### garcon-url-handler
Opens URLs in ChromeOS browser:
```bash
garcon-url-handler --client --url "https://example.com"
```

### garcon-terminal-handler
Terminal integration (used internally).

### Available Modes
```
--server     Run as daemon (internal)
--client     Send commands to ChromeOS host
  --url      Open URLs in browser
  --terminal Open new terminal
  --selectfile  Open file picker dialog
  --metrics  Report metrics to host
```

## VMC Commands (ChromeOS Crosh Only)

`vmc` is **not available from within Linux container** - it runs in crosh (Ctrl+Alt+T).

From crosh:
```
vmc start termina          # Start the VM
vmc stop termina           # Stop the VM
vmc list                   # List VMs
vmc container termina penguin  # Access container
vmc share termina Downloads    # Share folder (still requires UI confirmation)
vmc destroy termina        # Delete VM (destructive!)
```

**Note:** Even `vmc share` requires UI confirmation - no fully automated sharing.

## Installed Integration Packages

Key packages providing ChromeOS integration:
```
cros-garcon          # Bridge to ChromeOS
cros-guest-tools     # Metapackage for integration
cros-sommelier       # Wayland/X11 bridge for GUI apps
cros-pulse-config    # Audio integration
cros-sftp            # SFTP service
cros-notificationd   # Notification bridge
cros-im              # Input method support
```

## Limitations

| Feature | Status |
|---------|--------|
| Share folders from Linux | Not possible (security boundary) |
| Access unshared ChromeOS files | Not possible |
| Edit Google Docs/Sheets from terminal | Not possible (use APIs) |
| Run vmc from Linux container | Not possible (crosh only) |
| Automated folder sharing | Not possible without UI |

## Workarounds

### For Google Docs/Sheets Access
Use the GWSA MCP server or Google APIs directly:
```python
from gwsa.sdk import docs
content = docs.get_document_text(doc_id)
```

### For Automated File Access
1. Share the folder once via Files app UI (persists forever)
2. Then access freely from `/mnt/chromeos/...`

## Quick Reference

```bash
# Check what's shared
ls /mnt/chromeos/

# Open URL in browser
garcon-url-handler --client --url "https://google.com"

# Test Drive write access
echo "test" > /mnt/chromeos/GoogleDrive/MyDrive/test.txt

# List cros packages
dpkg -l | grep cros

# Check mount
mount | grep chromeos
```
