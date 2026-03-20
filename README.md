# Bugshot

Capture UI bugs from any live URL — including CSP-protected production and staging sites — and send them directly into Claude Code for fixing. No bookmarklet, no browser extension, no copy-paste.

## How it works

1. You tell Claude about a UI issue on a URL
2. Claude launches a real Chrome window via Playwright
3. You drag to select the broken area and describe the issue
4. Claude receives a pixel-perfect screenshot and structured report, then starts fixing

Playwright injects the capture overlay via Chrome DevTools Protocol (CDP), which bypasses Content-Security-Policy entirely. This means it works on every site, including production apps with strict CSP headers.

## Install

```bash
npx skills add grootan/bugshot
```

Then run the setup once to install Playwright and Chromium:

```bash
python3 install.py
```

## Usage

In Claude Code, say something like:

- "bugshot the issue on https://staging.myapp.com"
- "show you the bug on localhost:3000"
- "capture what's broken on production"

Claude opens a real Chrome window with a capture overlay. Here's the full flow:

1. **Drag to select** the broken area on the page
2. **Describe the issue** in the panel that slides up
3. **Set severity** (Low / Medium / High / Critical)
4. **Hit Cmd+Enter** (or Ctrl+Enter on Windows/Linux) to send

Once you hit send, the browser capture completes and you're **automatically taken back to your Claude Code session**. Claude receives the pixel-perfect screenshot and structured bug report, then immediately starts analyzing and fixing the issue — no manual copy-paste or context switching needed.

You can capture multiple issues in a single session. After each send, the overlay resets so you can select another area. Close the browser when you're done.

## Manual usage

```bash
# Capture from a specific URL
python3 scripts/capture.py https://your-url.com

# Interactive URL picker
python3 scripts/capture.py

# List detected project URLs
python3 scripts/capture.py --list-urls
```

## Output

The script produces:
- A structured report printed to stdout (URL, title, severity, region, description)
- A screenshot saved to `/tmp/bugshot-latest.png`

## Files

```
bugshot/
  install.py          # Cross-platform setup script
  install.sh          # Shell wrapper (macOS/Linux convenience)
  SKILL.md            # Skill definition for Claude Code
  README.md           # This file
  scripts/
    capture.py        # Main capture script
```

## Requirements

- Python 3
- macOS, Linux, or Windows with a display
