---
name: bugshot
description: >
  Capture a UI bug from any live URL — including CSP-protected production and staging sites —
  and inject it directly into Claude Code context with zero manual steps.
  Trigger when the user says anything like: "let me show you the bug", "I want to point
  at the issue", "capture what's broken on staging", "show you the UI problem", "screenshot
  the issue on production", "drag and select the problem", "bugshot this page", or any
  variation of wanting to visually show a UI problem on a running site. Opens a real visible
  Chrome window via Playwright, user drags to select the broken area, describes it, hits
  Send — screenshot and structured report arrive in Claude Code instantly. No bookmarklet,
  no extension, no copy-paste. Works on every URL including sites with strict
  Content-Security-Policy.
---

# Bugshot — Playwright Edition

Works on **every URL** including CSP-protected production sites.
No bookmarklet. No browser extension. No copy-paste.

---

## Requirements

Run `python3 install.py` once — it installs Playwright, Chromium, and the skill.
Works on macOS, Linux, and Windows.

---

## How Claude should use this skill

When the user wants to show a UI issue:

**Step 1 — Ask which URL (if not obvious from context):**

```bash
python3 /path/to/bugshot/scripts/capture.py --list-urls
```

Or just ask: *"Which URL should I open — your local dev server, staging, or production?"*

**Step 2 — Launch capture:**

```bash
python3 /path/to/bugshot/scripts/capture.py https://your-url.com
```

Tell the user:
> "Chrome just opened with a capture overlay. Drag over the broken area,
> describe the issue in the panel that appears, then hit ⌘↵ (or Ctrl+Enter on Windows).
> I'll get the screenshot and report instantly."

**Step 3 — Read result and fix:**

The script blocks until capture completes, then prints a structured report.
Screenshot is at `/tmp/bugshot-latest.png`.
Claude reads both and starts fixing immediately.

> **Note:** If the script reports that Playwright or Chromium is not installed,
> ask the user to run `python3 install.py` from the bugshot directory. Do NOT
> attempt to install Playwright or Chromium yourself.

---

## Why this works on production/CSP sites

Playwright injects the overlay via Chrome DevTools Protocol (CDP) using
`addInitScript` — this runs **before** any page scripts and **bypasses
Content-Security-Policy entirely**. The page cannot block it.

Contrast with bookmarklets: they run in the page's JavaScript context and
are blocked by CSP headers like `script-src 'self'`.

---

## Flow summary

```
User: "show you the issue on staging.myapp.com"
  → Claude runs capture.py https://staging.myapp.com
  → Real Chrome window opens, overlay injected (CSP bypassed)
  → User drags to select broken area → purple box appears
  → Description panel slides up
  → User types issue + sets severity → ⌘↵
  → Playwright takes pixel-perfect screenshot of selected region
  → Structured report printed to terminal
  → Claude reads report + screenshot → starts fixing
```

---

## Output

```
╔══════════════════════════════════════════════════════╗
║  🐛  UI Issue captured from live browser             ║
╚══════════════════════════════════════════════════════╝

  URL        : https://staging.myapp.com/dashboard
  Title      : Dashboard — MyApp
  Severity   : 🔴 High
  Region     : x=240, y=120, 480×200px
  Viewport   : 1440×900
  Timestamp  : 2025-06-15T09:42:11Z

  Issue description:
    Sidebar overlaps main content at 1280px width.
    z-index appears incorrect.

  Screenshot : /tmp/bugshot-latest.png
```
