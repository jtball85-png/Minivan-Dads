"""Print-QA gate for the garage's printable HTML reference sheets.

Renders an HTML file to PDF with real headless Edge (Chromium — the same
engine behind an ordinary Ctrl+P) and verifies the result BEFORE it's handed
over: exact page count, and every page at the expected physical size. Fails
loudly (nonzero exit, no PDF left behind) rather than silently shipping a
document that overflows onto an extra page or the wrong paper size.

This renders the LOCAL FILE directly (bypassing any hosting wrapper), which
is also why the verified PDF — not the hosted Artifact page — is the
recommended thing to actually print from: a PDF's pages are already fixed,
so there's no browser/print-dialog/wrapper re-flow risk left to test for.

Usage:
  .venv/Scripts/python.exe garage/prints/verify_print.py <html_path> \
      [--pages N] [--size WxH_in]   # defaults: 2 pages, 8.5x11 (Letter)
"""

from __future__ import annotations

import argparse
import glob
import subprocess
import sys
import time
from pathlib import Path

from pypdf import PdfReader

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str:
    for c in EDGE_CANDIDATES:
        if Path(c).exists():
            return c
    raise RuntimeError("No headless-capable Chromium browser found "
                       "(checked Edge and Chrome default install paths).")


def render_and_verify(html_path: Path, expect_pages: int, expect_w_in: float,
                       expect_h_in: float, tol_in: float = 0.05) -> Path:
    browser = find_browser()
    html_path = html_path.resolve()          # force absolute — GUI subprocess
    pdf_path = html_path.with_suffix(".pdf")  # cwd inheritance isn't reliable
    file_url = "file:///" + str(html_path).replace("\\", "/")

    pdf_path.unlink(missing_ok=True)  # never trust a stale file from a prior run
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--print-to-pdf-no-header", f"--print-to-pdf={pdf_path}", file_url],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"headless print failed (exit {result.returncode}): "
                           f"{result.stderr[:500]}")

    # Edge's PDF write finishes a beat after the process returns — poll rather
    # than guess a fixed sleep (that's exactly the bug this had before).
    deadline = time.time() + 10
    while time.time() < deadline and not (pdf_path.exists() and pdf_path.stat().st_size > 0):
        time.sleep(0.25)
    if not pdf_path.exists():
        raise RuntimeError(f"headless print exited 0 but no PDF appeared within "
                           f"10s at {pdf_path}. stderr: {result.stderr[:500]}")

    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    if n != expect_pages:
        pdf_path.unlink(missing_ok=True)
        raise AssertionError(f"FAIL: expected {expect_pages} page(s), got {n}. "
                             f"Content is overflowing — tighten sizing/spacing "
                             f"before shipping this file.")

    for i, page in enumerate(reader.pages):
        w_in, h_in = float(page.mediabox.width) / 72, float(page.mediabox.height) / 72
        if abs(w_in - expect_w_in) > tol_in or abs(h_in - expect_h_in) > tol_in:
            pdf_path.unlink(missing_ok=True)
            raise AssertionError(f"FAIL: page {i+1} is {w_in:.2f}x{h_in:.2f}in, "
                                 f"expected {expect_w_in}x{expect_h_in}in.")

    print(f"PASS: {pdf_path.name} — {n} page(s), {expect_w_in}x{expect_h_in}in each.")
    return pdf_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", help="HTML file to render+verify (or a glob)")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--size", default="8.5x11", help="expected WxH in inches")
    args = ap.parse_args()

    w_str, h_str = args.size.split("x")
    targets = [Path(p) for p in glob.glob(args.html)] or [Path(args.html)]
    failed = False
    for html_path in targets:
        try:
            render_and_verify(html_path, args.pages, float(w_str), float(h_str))
        except (RuntimeError, AssertionError) as e:
            print(f"{html_path.name}: {e}")
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
