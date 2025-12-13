# Quick Markdown Viewing from Command Line

## Requirements

1. **Launch from terminal** - Single command to view/edit a markdown file
2. **Minimal friction** - No navigating through menus or file dialogs
3. **Good rendering** - Either syntax-highlighted source or rendered preview
4. **Works on ChromeOS** - Compatible with Crostini Linux container
5. **Fast startup** - Should open quickly, not spin up a heavy IDE
6. **No workspace context** - Open the file directly, not within a previously loaded project/workspace

## Options

### Terminal-Based Options

#### Viewers (Read-Only)

| Tool | Install | Usage | Modes | Notes |
|------|---------|-------|-------|-------|
| **glow** | `go install github.com/charmbracelet/glow@latest` | `glow file.md` | Rendered | Best terminal renderer, pager built-in |
| **mdcat** | `cargo install mdcat` | `mdcat file.md` | Rendered | Good rendering, needs Rust |
| **bat** | `apt install bat` | `bat file.md` | Raw (highlighted) | Syntax highlighting, not rendered |
| **less/cat** | Built-in | `less file.md` | Raw | No highlighting |

#### Editors with Preview (Terminal-Based)

| Tool | Install | Usage | Notes |
|------|---------|-------|-------|
| **micro** | `apt install micro` | `micro file.md` | Modern terminal editor, no built-in preview but fast |
| **vim + vim-markdown** | Plugin | `:MarkdownPreview` | Preview in browser, stays in vim |
| **emacs + markdown-mode** | Package | Various | Full preview support |
| **mdt** | `go install github.com/mdt/mdt@latest` | `mdt file.md` | Terminal markdown editor with live preview |

#### HTML Viewing in Terminal

| Tool | Install | Usage | Notes |
|------|---------|-------|-------|
| **w3m** | `apt install w3m` | `w3m file.html` | Terminal web browser, renders HTML |
| **lynx** | `apt install lynx` | `lynx file.html` | Classic terminal browser |
| **elinks** | `apt install elinks` | `elinks file.html` | Another terminal browser |
| **pandoc + glow** | See below | Convert then view | Flexible pipeline |

**Pandoc pipeline for HTML → terminal:**
```bash
pandoc file.html -t markdown | glow -
```

### GUI Editors (Launch from CLI)

Open a GUI window from terminal command.

| Tool | Install | Usage | Notes |
|------|---------|-------|-------|
| **VSCode** | Already installed | `code file.md` | Full editor, preview with Ctrl+Shift+V |
| **Android Gravity** | Play Store | N/A | VSCode fork for Android/ChromeOS |
| **Typora** | Manual install | `typora file.md` | WYSIWYG markdown editor |
| **Marktext** | AppImage/deb | `marktext file.md` | Free, good preview |

**Heavy Editor Drawbacks (VSCode, Gravity, etc.):**
- Slow startup time (several seconds)
- May restore previous workspace context instead of opening file directly
- Overkill for quick file viewing
- `code -n file.md` opens in new window but still loads full IDE

### Browser-Based

Convert and open in browser.

| Tool | Install | Usage | Notes |
|------|---------|-------|-------|
| **grip** | `pip install grip` | `grip file.md -b` | GitHub-flavored, needs internet |
| **pandoc + browser** | `apt install pandoc` | See below | Offline, flexible |

**Pandoc one-liner:**
```bash
pandoc file.md -o /tmp/view.html && garcon-url-handler --client --url "file:///tmp/view.html"
```

## Analysis

### Already Available
- **VSCode** - `code file.md` works now, good preview mode

### Easy to Add
- **glow** - Best terminal option, single binary, no dependencies
- **grip** - Python-based, easy pip install
- **bat** - Available via apt (may be `batcat` on Debian)

### Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| Terminal (glow) | Fast, stays in terminal, no context | No clickable links, limited formatting |
| GUI (VSCode) | Full editing, preview | Heavy, slow, may load workspace |
| Browser (grip) | Best rendering | Needs internet, slower startup |
| Browser (pandoc) | Offline, fast conversion | Extra step, temp file |

## Recommendations

### Best for Quick View: glow (Terminal)
Fastest option - instant startup, no workspace context, stays in terminal:
```bash
# Via Go
go install github.com/charmbracelet/glow@latest

# Or download binary
curl -sL https://github.com/charmbracelet/glow/releases/latest/download/glow_Linux_x86_64.tar.gz | tar xz
sudo mv glow /usr/local/bin/
```

Then: `glow file.md`

### For Editing (When Needed)
VSCode works but is heavy. Consider:
```bash
# New window, no workspace restore
code -n file.md

# Or use nano/vim for quick edits
nano file.md
```

### Shell Alias Suggestion
Add to `~/.bashrc`:
```bash
# Quick markdown view (fast, lightweight)
alias mdv='glow'

# Quick markdown edit (lightweight)
alias mde='nano'
```

## Status

- [ ] Install glow
- [ ] Test grip for browser rendering
- [ ] Add shell aliases
