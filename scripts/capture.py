#!/usr/bin/env python3
"""
Bugshot — Playwright edition
Works on ANY URL including CSP-protected production sites.

How it works:
  1. Opens the target URL in a REAL visible Chrome window
  2. Injects a selection overlay via Playwright's CDP bypass (ignores CSP)
  3. User drags to select the problem area and describes the issue
  4. Playwright takes a pixel-perfect screenshot of exactly that region
  5. Prints structured report to stdout for Claude Code

Usage:
    python3 capture.py <url>
    python3 capture.py                  # interactive URL picker
    python3 capture.py --list-urls      # show detected project URLs
"""

import sys, os, json, base64, time, re, argparse, tempfile, threading
from pathlib import Path

# ── Try importing playwright ─────────────────────────────────────────────────
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("❌  Playwright not found. Install it with:")
    print("    pip3 install playwright")
    print("    playwright install chromium")
    sys.exit(1)

SKILL_DIR   = Path(__file__).parent.parent

# ── URL detection ────────────────────────────────────────────────────────────
def detect_urls() -> list[str]:
    urls = []
    # package.json dev scripts
    for pkg in [Path("package.json"), Path("../package.json")]:
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                for v in data.get("scripts", {}).values():
                    for m in re.findall(r'https?://[^\s"\'\\]+', v):
                        urls.append(m)
            except Exception:
                pass
    # .env files
    for env in [Path(".env"), Path(".env.local"), Path("../.env")]:
        if env.exists():
            for line in env.read_text().splitlines():
                for m in re.findall(r'https?://[^\s"\'\\]+', line):
                    urls.append(m)
    # common localhost ports
    for port in [3000, 3001, 4200, 5173, 8080, 8000, 5000, 4000]:
        urls.append(f"http://localhost:{port}")

    seen, result = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); result.append(u)
    return result


def pick_url(extra: list[str]) -> str:
    detected = detect_urls()
    candidates = extra + [u for u in detected if u not in extra]
    options = candidates[:9]

    print("\n╔══════════════════════════════════════════════════╗")
    print("║  🎯  Bugshot — which URL should I open?            ║")
    print("╚══════════════════════════════════════════════════╝\n")
    for i, u in enumerate(options, 1):
        print(f"  {i}. {u}")
    print(f"  {len(options)+1}. Enter a different URL\n")

    while True:
        raw = input("  Pick a number (or paste a URL): ").strip()
        if raw.startswith("http"):
            return raw
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
            elif idx == len(options) + 1:
                return input("  URL: ").strip()
        except ValueError:
            pass
        print("  ⚠️  Try again.")


# ── Overlay injection script ─────────────────────────────────────────────────
# Injected via Playwright's addInitScript — runs BEFORE page scripts,
# bypasses Content-Security-Policy entirely (CDP level injection).
OVERLAY_JS = r"""
(function() {
  if (window.__uiCaptureReady) return;
  window.__uiCaptureReady = true;

  // ── State ──────────────────────────────────────────────────────────
  let drag = null, committed = null, capturing = false;
  const result = { done: false, data: null };
  window.__uiCaptureResult = result;

  // ── Wait for body to exist before injecting UI ────────────────────
  function init() {
    if (document.getElementById('__uc_root')) return;

  // ── CSS ────────────────────────────────────────────────────────────
  const Z = 2147483640;
  const style = document.createElement('style');
  style.textContent = `
    #__uc_root * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    #__uc_bar {
      position: fixed; top: 8px; left: 50%; transform: translateX(-50%); z-index: ${Z};
      height: 34px; background: rgba(13,13,26,.92);
      border: 1px solid rgba(124,58,237,.4);
      border-radius: 20px;
      display: flex; align-items: center; gap: 8px; padding: 0 6px 0 12px;
      box-shadow: 0 2px 20px rgba(0,0,0,.6);
      backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
      pointer-events: auto;
    }
    #__uc_bar.capturing { border-color: rgba(168,85,247,.7); box-shadow: 0 2px 20px rgba(168,85,247,.4); }
    #__uc_bar_logo { font-size: 14px; }
    #__uc_bar_title { font-size: 12px; font-weight: 700; color: #e2e8f0; }
    #__uc_bar_hint { font-size:11px; color:#7c3aed; }
    #__uc_bar_hint.pulse { animation: __uc_pulse 2s infinite; }
    @keyframes __uc_pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
    #__uc_bar_capture {
      padding: 3px 10px; border-radius: 12px;
      background: linear-gradient(135deg,#7c3aed,#5b21b6);
      border: none; color: #fff; font-size: 11px; font-weight: 700;
      cursor: pointer; font-family: inherit; transition: opacity .15s;
    }
    #__uc_bar_capture:hover { opacity: .85; }
    #__uc_bar_capture.active {
      background: rgba(255,255,255,.08);
      color: #a78bfa;
      border: 1px solid rgba(167,139,250,.3);
    }
    #__uc_bar_close {
      width:22px; height:22px; border-radius:50%;
      background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1);
      color:#94a3b8; font-size:11px; cursor:pointer;
      display:flex; align-items:center; justify-content:center;
      transition:all .15s;
    }
    #__uc_bar_close:hover { background:rgba(239,68,68,.2); color:#f87171; }
    #__uc_dim {
      position: fixed; top:0; left:0; right:0; bottom:0; z-index:${Z-1};
      cursor: crosshair; background: rgba(0,0,0,0);
      pointer-events: none; display: none;
      transition: background .2s;
    }
    #__uc_dim.capturing { display: block; pointer-events: auto; }
    #__uc_dim.active { background: rgba(0,0,0,.5); }
    #__uc_chH { position:fixed; height:1px; left:0; right:0; z-index:${Z+2}; background:rgba(167,139,250,.45); pointer-events:none; display:none; }
    #__uc_chV { position:fixed; width:1px;  top:0; bottom:0; z-index:${Z+2}; background:rgba(167,139,250,.45); pointer-events:none; display:none; }
    #__uc_sel {
      position:fixed; z-index:${Z+3};
      border:2px solid #a855f7;
      box-shadow: 0 0 0 9999px rgba(0,0,0,.5), 0 0 16px rgba(168,85,247,.4);
      border-radius:3px; display:none; pointer-events:none;
    }
    #__uc_badge {
      position:fixed; z-index:${Z+4};
      background:#1e1333; border:1px solid #4c1d95;
      color:#c4b5fd; font-size:11px; font-weight:700;
      padding:3px 8px; border-radius:4px; pointer-events:none;
      display:none; font-family: monospace;
    }
    #__uc_panel {
      position:fixed; bottom:-280px; left:50%; transform:translateX(-50%);
      width:min(500px, 94vw); z-index:${Z+5};
      background: #0d0d1a;
      border:1px solid rgba(167,139,250,.3);
      border-radius:16px 16px 0 0;
      padding:8px 20px 22px;
      box-shadow: 0 -12px 50px rgba(109,40,217,.3);
      transition: bottom .35s cubic-bezier(.32,1.1,.4,1);
    }
    #__uc_panel.open { bottom:0; }
    #__uc_handle { width:38px; height:4px; border-radius:2px; background:rgba(167,139,250,.25); margin:10px auto 14px; }
    #__uc_ptitle { font-size:14px; font-weight:700; color:#e2e8f0; margin-bottom:10px; display:flex; align-items:center; gap:8px; }
    #__uc_chip { font-size:11px; font-weight:600; background:rgba(109,40,217,.25); color:#a78bfa; border:1px solid rgba(109,40,217,.5); border-radius:4px; padding:2px 8px; font-family:monospace; }
    #__uc_ta {
      width:100%; background:rgba(255,255,255,.04); border:1px solid rgba(167,139,250,.25);
      border-radius:10px; padding:10px 12px; color:#e2e8f0; font-size:13px;
      line-height:1.6; resize:none; height:84px; font-family:inherit;
      transition:border-color .2s;
    }
    #__uc_ta:focus { outline:none; border-color:rgba(167,139,250,.7); }
    #__uc_ta::placeholder { color:#4c3a6e; }
    #__uc_row { display:flex; gap:8px; margin-top:10px; align-items:center; }
    #__uc_sev {
      background:rgba(255,255,255,.04); border:1px solid rgba(167,139,250,.25);
      border-radius:8px; color:#a78bfa; font-size:12px; padding:8px 10px;
      cursor:pointer; min-width:120px; font-family:inherit;
    }
    #__uc_retake {
      padding:9px 14px; background:rgba(255,255,255,.05);
      border:1px solid rgba(255,255,255,.1); border-radius:8px;
      color:#64748b; font-size:12px; font-weight:600; cursor:pointer;
      font-family:inherit; transition:all .15s;
    }
    #__uc_retake:hover { background:rgba(255,255,255,.09); color:#94a3b8; }
    #__uc_send {
      flex:1; padding:10px 14px;
      background:linear-gradient(135deg,#7c3aed,#5b21b6);
      border:none; border-radius:8px; color:#fff;
      font-size:13px; font-weight:700; cursor:pointer;
      display:flex; align-items:center; justify-content:center; gap:7px;
      font-family:inherit; box-shadow:0 4px 16px rgba(109,40,217,.4);
      transition:opacity .2s;
    }
    #__uc_send:hover { opacity:.88; }
    #__uc_send:disabled { opacity:.4; cursor:not-allowed; }
    #__uc_shortcut {
      font-size:10px; color:rgba(255,255,255,.35);
      background:rgba(255,255,255,.07); border-radius:3px; padding:1px 5px;
    }
  `;
  document.head.appendChild(style);

  // ── DOM ────────────────────────────────────────────────────────────
  const root = document.createElement('div');
  root.id = '__uc_root';
  root.innerHTML = `
    <div id="__uc_bar">
      <div id="__uc_bar_logo">📐</div>
      <div id="__uc_bar_title">Bugshot</div>
      <div id="__uc_bar_hint">Browse the page, then capture</div>
      <button id="__uc_bar_capture">Capture</button>
      <div id="__uc_bar_close" title="End session">✕</div>
    </div>
    <div id="__uc_dim"></div>
    <div id="__uc_chH"></div>
    <div id="__uc_chV"></div>
    <div id="__uc_sel"></div>
    <div id="__uc_badge"></div>
    <div id="__uc_panel">
      <div id="__uc_handle"></div>
      <div id="__uc_ptitle">🐛 Describe the issue <span id="__uc_chip"></span></div>
      <textarea id="__uc_ta" placeholder="e.g. Nav bar overlaps content on scroll. z-index looks wrong."></textarea>
      <div id="__uc_row">
        <select id="__uc_sev">
          <option value="low">🟢 Low</option>
          <option value="medium" selected>🟡 Medium</option>
          <option value="high">🔴 High</option>
          <option value="critical">🚨 Critical</option>
        </select>
        <button id="__uc_retake">✕ Retake</button>
        <button id="__uc_send">⚡ Send to Claude Code <span id="__uc_shortcut">⌘↵</span></button>
      </div>
    </div>
  `;
  document.body.appendChild(root);

  const bar    = document.getElementById('__uc_bar');
  const dim    = document.getElementById('__uc_dim');
  const sel    = document.getElementById('__uc_sel');
  const chH    = document.getElementById('__uc_chH');
  const chV    = document.getElementById('__uc_chV');
  const badge  = document.getElementById('__uc_badge');
  const panel  = document.getElementById('__uc_panel');
  const chip   = document.getElementById('__uc_chip');
  const ta     = document.getElementById('__uc_ta');
  const sevEl  = document.getElementById('__uc_sev');
  const btnSend= document.getElementById('__uc_send');
  const btnRet = document.getElementById('__uc_retake');
  const hint   = document.getElementById('__uc_bar_hint');
  const btnCap = document.getElementById('__uc_bar_capture');
  const closeB = document.getElementById('__uc_bar_close');

  // ── Capture mode toggle ───────────────────────────────────────────
  function enterCaptureMode() {
    capturing = true;
    dim.classList.add('capturing');
    bar.classList.add('capturing');
    btnCap.textContent = 'Cancel';
    btnCap.classList.add('active');
    hint.textContent = 'Drag to select the problem area';
    hint.classList.add('pulse');
  }

  function exitCaptureMode() {
    capturing = false;
    dim.classList.remove('capturing', 'active');
    bar.classList.remove('capturing');
    btnCap.textContent = 'Capture';
    btnCap.classList.remove('active');
    hint.textContent = 'Browse the page, then capture';
    hint.classList.remove('pulse');
    sel.style.display = 'none';
    chH.style.display = chV.style.display = 'none';
    badge.style.display = 'none';
    drag = null;
    committed = null;
  }

  btnCap.addEventListener('click', () => {
    if (capturing) exitCaptureMode();
    else enterCaptureMode();
  });

  // ── Crosshairs ─────────────────────────────────────────────────────
  dim.addEventListener('mousemove', e => {
    if (drag) return;
    chH.style.display='block'; chH.style.top  = e.clientY+'px';
    chV.style.display='block'; chV.style.left = e.clientX+'px';
  });
  dim.addEventListener('mouseleave', () => { chH.style.display=chV.style.display='none'; });

  // ── Drag ───────────────────────────────────────────────────────────
  dim.addEventListener('mousedown', e => {
    e.preventDefault();
    drag = { x0: e.clientX, y0: e.clientY };
    dim.classList.add('active');
    chH.style.display = chV.style.display = 'none';
  });

  document.addEventListener('mousemove', e => {
    if (!drag) return;
    updateSel(drag.x0, drag.y0, e.clientX, e.clientY);
    badge.style.display='block';
    badge.style.left=(e.clientX+10)+'px';
    badge.style.top =(e.clientY+10)+'px';
    const w=Math.abs(e.clientX-drag.x0), h=Math.abs(e.clientY-drag.y0);
    badge.textContent=`${Math.round(w)} × ${Math.round(h)}`;
  });

  document.addEventListener('mouseup', e => {
    if (!drag) return;
    const w=Math.abs(e.clientX-drag.x0), h=Math.abs(e.clientY-drag.y0);
    badge.style.display='none';
    if (w<20||h<20) { drag=null; sel.style.display='none'; dim.classList.remove('active'); return; }
    committed = {
      viewX: Math.min(drag.x0,e.clientX), viewY: Math.min(drag.y0,e.clientY),
      width: Math.round(w), height: Math.round(h),
      pageX: Math.round(Math.min(drag.x0,e.clientX)+window.scrollX),
      pageY: Math.round(Math.min(drag.y0,e.clientY)+window.scrollY),
    };
    drag = null;
    chip.textContent = `${committed.width} × ${committed.height} px`;
    hint.textContent = 'Describe the issue below';
    hint.classList.remove('pulse');
    panel.classList.add('open');
    setTimeout(()=>ta.focus(), 360);
  });

  function updateSel(x0,y0,x1,y1) {
    const x=Math.min(x0,x1), y=Math.min(y0,y1), w=Math.abs(x1-x0), h=Math.abs(y1-y0);
    sel.style.cssText=`display:block;left:${x}px;top:${y}px;width:${w}px;height:${h}px`;
  }

  // ── Panel ──────────────────────────────────────────────────────────
  function resetPanel() {
    panel.classList.remove('open');
    exitCaptureMode();
    ta.value='';
    btnSend.disabled=false;
    btnSend.innerHTML='⚡ Send to Claude Code <span id="__uc_shortcut" style="font-size:10px;color:rgba(255,255,255,.35);background:rgba(255,255,255,.07);border-radius:3px;padding:1px 5px">⌘↵</span>';
  }

  btnRet.addEventListener('click', resetPanel);
  closeB.addEventListener('click', () => { result.done=true; result.data=null; root.remove(); });

  // ── Send ───────────────────────────────────────────────────────────
  btnSend.addEventListener('click', send);
  document.addEventListener('keydown', e => {
    if (e.key==='Escape') { if (panel.classList.contains('open')) resetPanel(); else if (capturing) exitCaptureMode(); }
    if ((e.metaKey||e.ctrlKey) && e.key==='Enter' && committed) send();
    if ((e.altKey||e.ctrlKey) && e.key==='c' && !committed && !e.shiftKey) {
      e.preventDefault();
      if (capturing) exitCaptureMode(); else enterCaptureMode();
    }
  });

  function send() {
    const desc = ta.value.trim();
    if (!desc) { ta.style.borderColor='#ef4444'; ta.focus(); setTimeout(()=>ta.style.borderColor='',1500); return; }
    btnSend.disabled=true;
    btnSend.innerHTML='⏳ Sending…';
    result.done = true;
    result.data = {
      url:         location.href,
      title:       document.title,
      description: desc,
      severity:    sevEl.value,
      region:      committed,
      timestamp:   new Date().toISOString(),
      viewport:    { width: window.innerWidth, height: window.innerHeight },
      scrollX:     window.scrollX,
      scrollY:     window.scrollY,
    };
  }
  } // end init()

  // Boot: try now, DOMContentLoaded, and poll as fallback
  if (document.body) { init(); }
  else {
    document.addEventListener('DOMContentLoaded', init);
    const _poll = setInterval(() => { if (document.body) { clearInterval(_poll); init(); } }, 50);
  }
})();
"""


# ── Main capture flow ────────────────────────────────────────────────────────
def take_screenshot(page, result_data: dict, capture_num: int) -> dict:
    """Hide overlay, take screenshot, restore overlay, return enriched result."""
    region = result_data.get("region", {})
    clip = None
    if region and region.get("width") and region.get("height"):
        clip = {
            "x":      region["viewX"],
            "y":      region["viewY"],
            "width":  region["width"],
            "height": region["height"],
        }

    # Hide overlay before screenshot
    try:
        page.evaluate("() => { const r = document.getElementById('__uc_root'); if (r) r.style.display = 'none'; }")
        time.sleep(0.15)
    except Exception:
        pass

    screenshot_b64 = None
    try:
        img_bytes = page.screenshot(type="png", clip=clip, full_page=(clip is None))
        screenshot_b64 = base64.b64encode(img_bytes).decode()

        img_path = Path(f"/tmp/bugshot-{capture_num}.png")
        img_path.write_bytes(img_bytes)
        # Also save as latest for easy access
        Path("/tmp/bugshot-latest.png").write_bytes(img_bytes)
        print(f"📸  Screenshot → {img_path}", flush=True)
    except Exception as e:
        print(f"⚠️  Screenshot failed: {e}", flush=True)

    # Restore overlay and reset to browse mode for next capture
    try:
        page.evaluate("""() => {
            const r = document.getElementById('__uc_root');
            if (r) r.style.display = '';
            window.__uiCaptureResult.done = false;
            window.__uiCaptureResult.data = null;
            const panel = document.getElementById('__uc_panel');
            if (panel) panel.classList.remove('open');
            const sel = document.getElementById('__uc_sel');
            if (sel) sel.style.display = 'none';
            const dim = document.getElementById('__uc_dim');
            if (dim) dim.classList.remove('capturing', 'active');
            const bar = document.getElementById('__uc_bar');
            if (bar) bar.classList.remove('capturing');
            const ta = document.getElementById('__uc_ta');
            if (ta) ta.value = '';
            const hint = document.getElementById('__uc_bar_hint');
            if (hint) { hint.textContent = 'Browse the page, then capture'; hint.classList.remove('pulse'); }
            const cap = document.getElementById('__uc_bar_capture');
            if (cap) { cap.textContent = 'Capture'; cap.classList.remove('active'); }
            const btn = document.getElementById('__uc_send');
            if (btn) { btn.disabled = false; btn.innerHTML = '⚡ Send to Claude Code <span style="font-size:10px;color:rgba(255,255,255,.35);background:rgba(255,255,255,.07);border-radius:3px;padding:1px 5px">⌘↵</span>'; }
        }""")
    except Exception:
        pass

    result_data["screenshot_b64"] = screenshot_b64
    return result_data


def capture(url: str) -> list[dict]:
    print(f"\n🌐  Opening: {url}", flush=True)
    print(f"📐  Drag to select the broken area, describe it, then hit ⌘↵ or click Send.", flush=True)
    print(f"    Session stays open — capture as many issues as you want.", flush=True)
    print(f"    Click ✕ or close the browser to end the session.\n", flush=True)

    results = []

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
            )
        except Exception as e:
            if "Executable doesn't exist" in str(e) or "browserType.launch" in str(e):
                print("❌  Chromium browser not installed for Playwright.")
                print("    Run the setup script first:")
                print("    python3 install.py")
                sys.exit(1)
            raise
        ctx = browser.new_context(
            no_viewport=True,
            ignore_https_errors=True,
        )

        ctx.add_init_script(OVERLAY_JS)
        page = ctx.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except PWTimeout:
            print("⚠️  Page load timed out — overlay still active, proceed with capture.", flush=True)
        except Exception as e:
            print(f"⚠️  Navigation warning: {e}", flush=True)

        capture_num = 0
        session_active = True

        while session_active:
            capture_num += 1
            if capture_num == 1:
                print("⏳  Waiting for you to select and describe the issue…", flush=True)
            else:
                print(f"\n⏳  Ready for capture #{capture_num} — drag to select another issue…", flush=True)

            # Poll until user completes or cancels
            result_data = None
            while True:
                time.sleep(0.5)
                try:
                    if not browser.is_connected():
                        session_active = False
                        break
                    done = page.evaluate("() => window.__uiCaptureResult && window.__uiCaptureResult.done")
                    if done:
                        result_data = page.evaluate("() => window.__uiCaptureResult.data")
                        break
                except Exception:
                    try:
                        if not browser.is_connected():
                            session_active = False
                            break
                    except Exception:
                        session_active = False
                        break
                    continue

            if not session_active:
                break

            # data=null means user clicked close
            if not result_data:
                session_active = False
                break

            result_data = take_screenshot(page, result_data, capture_num)
            results.append(result_data)
            print(format_report(result_data), flush=True)

        try:
            browser.close()
        except Exception:
            pass

        total = len(results)
        if total == 0:
            print("\n⚠️  Session ended — no captures.", flush=True)
        else:
            print(f"\n✅  Session ended — {total} issue{'s' if total != 1 else ''} captured.", flush=True)

        return results


def format_report(r: dict) -> str:
    sev_map = {"low":"🟢 Low","medium":"🟡 Medium","high":"🔴 High","critical":"🚨 Critical"}
    sev = sev_map.get(r.get("severity","medium"), r.get("severity",""))
    region = r.get("region") or {}
    reg_str = (f"x={region.get('pageX')}, y={region.get('pageY')}, "
               f"{region.get('width')}×{region.get('height')}px") if region else "full page"
    vp = r.get("viewport", {})

    return "\n".join([
        "",
        "╔══════════════════════════════════════════════════════╗",
        "║  🐛  UI Issue captured from live browser             ║",
        "╚══════════════════════════════════════════════════════╝",
        "",
        f"  URL        : {r.get('url','')}",
        f"  Title      : {r.get('title','')}",
        f"  Severity   : {sev}",
        f"  Region     : {reg_str}",
        f"  Viewport   : {vp.get('width')}×{vp.get('height')}",
        f"  Timestamp  : {r.get('timestamp','')}",
        "",
        "  Issue description:",
        *[f"    {l}" for l in r.get("description","").splitlines()],
        "",
        f"  Screenshot : /tmp/bugshot-latest.png",
        "",
        "  ➜  Fix the issue described above. Use the screenshot",
        "     to locate the exact element. Explain what changed.",
        "",
        "━"*56,
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--list-urls", action="store_true")
    args = ap.parse_args()

    if args.list_urls:
        for u in detect_urls(): print(u)
        return

    url = args.url or pick_url([])
    capture(url)


if __name__ == "__main__":
    main()
