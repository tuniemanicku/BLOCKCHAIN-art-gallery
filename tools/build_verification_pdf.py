"""Render results/weryfikacja-systemu.md to results/weryfikacja-systemu.pdf.

Needs the `Markdown` package (pip install markdown) and Microsoft Edge or Google Chrome
(used in headless mode to print the HTML to PDF).
"""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import markdown

RESULTS = Path(__file__).resolve().parent.parent / "results"
SOURCE = RESULTS / "weryfikacja-systemu.md"
TARGET = RESULTS / "weryfikacja-systemu.pdf"
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge", "google-chrome", "chromium",
]
STYLE = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 19pt; border-bottom: 2px solid #1565c0; padding-bottom: 4px; }
h2 { font-size: 14.5pt; color: #1565c0; margin-top: 22px; page-break-after: avoid; }
h3 { font-size: 12.5pt; margin-top: 18px; page-break-after: avoid; }
h4 { font-size: 11pt; margin: 16px 0 4px; padding: 4px 8px; background: #eef3fb; border-left: 4px solid #1565c0;
     page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #c8c8c8; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #f1f1f1; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f4f4f4; padding: 0 3px; }
pre { background: #f4f4f4; padding: 8px; border-radius: 4px; }
pre code { padding: 0; }
a { color: #1565c0; text-decoration: none; }
"""


def find_browser() -> str:
    for candidate in BROWSERS:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    raise SystemExit("Edge or Chrome not found")


def main() -> None:
    body = markdown.markdown(SOURCE.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"])
    html = (f"<!doctype html><html lang='pl'><head><meta charset='utf-8'>"
            f"<title>Sellart - weryfikacja systemu</title><style>{STYLE}</style></head>"
            f"<body>{body}</body></html>")
    work_dir = Path(tempfile.mkdtemp(prefix="sellart-pdf-"))
    page = work_dir / "doc.html"
    page.write_text(html, encoding="utf-8")
    TARGET.unlink(missing_ok=True)
    subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--user-data-dir={work_dir / 'profile'}", f"--print-to-pdf={TARGET}", page.as_uri()],
                   capture_output=True, timeout=120)
    # The browser may hand the job to a child process - wait for the file to appear.
    deadline = time.time() + 60
    while not TARGET.exists() and time.time() < deadline:
        time.sleep(0.5)
    time.sleep(1)
    shutil.rmtree(work_dir, ignore_errors=True)
    if not TARGET.exists():
        raise SystemExit("the browser did not produce the PDF")
    print(f"written {TARGET}")


if __name__ == "__main__":
    main()
