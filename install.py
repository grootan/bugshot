#!/usr/bin/env python3
"""
Bugshot — cross-platform setup script.
Works on macOS, Linux, and Windows.

Usage:
    python3 install.py
"""

import subprocess, sys, shutil
from pathlib import Path


def run(cmd, **kwargs):
    print(f"  $ {' '.join(cmd)}")
    subprocess.check_call(cmd, **kwargs)


def main():
    print()
    print("🎯  Bugshot — Setup")
    print("━" * 38)

    # 1. Check Python version
    if sys.version_info < (3, 8):
        print(f"❌  Python 3.8+ required (found {sys.version})")
        sys.exit(1)
    print(f"✅  Python {sys.version.split()[0]}")

    # 2. Install playwright pip package
    print()
    print("📦  Installing Playwright...")
    try:
        run([sys.executable, "-m", "pip", "install", "playwright", "--quiet",
             "--break-system-packages"], stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, Exception):
        run([sys.executable, "-m", "pip", "install", "playwright", "--quiet"])
    print("✅  Playwright installed")

    # 3. Install Chromium for Python Playwright
    print()
    print("🌐  Installing Chromium (one-time, ~150 MB)...")
    run([sys.executable, "-m", "playwright", "install", "chromium"])
    print("✅  Chromium ready")

    # 4. Copy skill into Claude Code skills directory
    #    ~/.claude/skills/ works on all platforms (Path.home() is cross-platform)
    skill_dir = Path.home() / ".claude" / "skills"
    target = skill_dir / "bugshot"
    source = Path(__file__).resolve().parent

    print()
    print("🔧  Installing skill into Claude Code...")
    skill_dir.mkdir(parents=True, exist_ok=True)

    if target.exists():
        print("   Removing existing installation...")
        shutil.rmtree(target)

    shutil.copytree(source, target)
    print(f"✅  Skill installed → {target}")

    print()
    print("━" * 38)
    print('🎉  All done! Restart Claude Code, then say:')
    print('    "bugshot the issue on https://your-url.com"')
    print()


if __name__ == "__main__":
    main()
