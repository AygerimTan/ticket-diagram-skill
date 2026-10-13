#!/usr/bin/env python3
"""Screenshot a local HTML page with headless Chrome/Chromium/Edge.

Usage: screenshot.py <page.html> <out.png> [WIDTHxHEIGHT]   (default 1440x900)
       screenshot.py --selfcheck

Browser: $ARCHIFY_CHROME (the variable archify's visual-check reads), then $CHROME_PATH, then the
usual macOS / Windows / Linux locations. A variable that is set must point at a browser — no
silent fallback. ARCHIFY_CHROME_NO_SANDBOX=1 adds --no-sandbox (root / containers), as in archify.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ON_PATH = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge"]


def candidates():
    yield "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    yield "/Applications/Chromium.app/Contents/MacOS/Chromium"
    yield "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.environ.get(var)
        if root:
            yield os.path.join(root, "Google", "Chrome", "Application", "chrome.exe")
            yield os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe")


def find_browser():
    for var in ("ARCHIFY_CHROME", "CHROME_PATH"):
        if var in os.environ:
            if Path(os.environ[var]).is_file():
                return os.environ[var]
            sys.exit(f"${var} is set but is not a file: {os.environ[var]!r}")
    for c in candidates():
        if Path(c).is_file():
            return c
    for name in ON_PATH:
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("no Chrome/Chromium/Edge found — set ARCHIFY_CHROME, or screenshot with agent-browser/playwright")


def parse_size(arg):
    m = re.fullmatch(r"(\d+)x(\d+)", arg.strip())
    if not m:
        sys.exit(f"size must be WIDTHxHEIGHT, e.g. 1440x900 — got {arg!r}")
    return m.groups()


def shoot(page, out, size="1440x900"):
    page, out = Path(page).resolve(), Path(out).resolve()
    if not page.is_file():
        sys.exit(f"no such page: {page}")
    w, h = parse_size(size)
    out.parent.mkdir(parents=True, exist_ok=True)  # Chrome exits 0 without writing into a missing dir
    cmd = [find_browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
           f"--window-size={w},{h}", "--virtual-time-budget=3000", f"--screenshot={out}", page.as_uri()]
    if os.environ.get("ARCHIFY_CHROME_NO_SANDBOX") == "1":
        cmd.insert(1, "--no-sandbox")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        sys.exit("browser timed out after 120s")
    if r.returncode:
        sys.exit(f"browser failed ({r.returncode}): {r.stderr.strip()[-800:]}")
    if not out.is_file():
        sys.exit(f"browser exited 0 but wrote no file: {out}\n{(r.stdout + r.stderr).strip()[-800:]}")
    return out


def _selfcheck():
    import tempfile

    def exits(fn, *a):
        try:
            fn(*a)
        except SystemExit as e:
            return str(e)
        return None

    assert parse_size("1440x830") == ("1440", "830")
    for bad in ("1440", "1440x900x2", "abcxdef"):
        assert "WIDTHxHEIGHT" in exits(parse_size, bad), bad
    with tempfile.TemporaryDirectory() as d:
        page = Path(d) / "p.html"
        page.write_text("<p>ok</p>")
        fake = Path(d) / "fake-browser"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        saved = {k: os.environ.pop(k, None) for k in ("ARCHIFY_CHROME", "CHROME_PATH")}
        try:
            os.environ["ARCHIFY_CHROME"] = str(Path(d) / "missing")
            assert "ARCHIFY_CHROME is set" in exits(find_browser)
            if os.name == "posix":
                os.environ["ARCHIFY_CHROME"] = str(fake)
                assert "wrote no file" in exits(shoot, page, Path(d) / "o.png")
            del os.environ["ARCHIFY_CHROME"]
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
            if exits(find_browser):
                print("selfcheck ok (no browser found — real screenshot skipped)")
                return
            out = shoot(page, Path(d) / "checks" / "real.png", "320x200")   # parent doesn't exist yet
            assert out.stat().st_size > 0
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
    print("selfcheck ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        _selfcheck()
        sys.exit()
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    print(shoot(*sys.argv[1:4]))
