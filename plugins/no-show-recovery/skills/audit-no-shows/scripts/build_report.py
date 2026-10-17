#!/usr/bin/env python3
"""Build the No-Show Recovery report: one self-contained HTML file.

Every number comes from audit.json (written by audit.py). Standard library only.

Usage:
  build_report.py AUDIT_JSON [--open]

Writes report.html next to AUDIT_JSON.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "report-template.html"
CTA = HERE.parent / "assets" / "cta.json"


def open_file(path: Path) -> None:
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        elif platform.system() == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audit")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    src = Path(a.audit)
    data = json.loads(src.read_text(encoding="utf-8"))
    data["cta"] = json.loads(CTA.read_text(encoding="utf-8")) if CTA.exists() else None
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__AUDIT_DATA__*/null", payload)
    out = src.parent / "report.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}")
    if a.open:
        open_file(out)


if __name__ == "__main__":
    main()
