#!/usr/bin/env python3
"""Download the latest NCBI AMRFinderPlus reference database (HTTPS).

Docs: https://github.com/ncbi/amr/wiki/AMRFinderPlus-database
URL:  https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/AMRFinderPlus/database/latest/
"""

from __future__ import annotations

import argparse
import hashlib
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

BASE = (
    "https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/"
    "AMRFinderPlus/database/latest/"
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for k, v in attrs:
            if k == "href" and v:
                self.hrefs.append(v)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_files(url: str) -> list[str]:
    with urllib.request.urlopen(url, timeout=120) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(html)
    files: list[str] = []
    for href in parser.hrefs:
        if href in ("../", "./") or href.endswith("/"):
            continue
        if href.startswith("?") or href.startswith("/"):
            continue
        # Skip directory parent links and query noise
        if re.match(r"^[\w.\-+=]+$", href):
            files.append(href)
    return sorted(set(files))


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")

    req = urllib.request.Request(url, headers={"User-Agent": "GenomeFirewall/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        total = resp.headers.get("Content-Length")
        total_i = int(total) if total else None
        if dest.exists() and total_i and dest.stat().st_size == total_i:
            print(f"[skip] {dest.name}")
            return
        print(f"[get]  {dest.name}" + (f" ({total_i:,} bytes)" if total_i else ""))
        with tmp.open("wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    tmp.replace(dest)
    digest = sha256_file(dest)
    print(f"[ok]   {dest.name} sha256={digest}")
    (dest.with_suffix(dest.suffix + ".sha256")).write_text(f"{digest}  {dest.name}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/raw/amrfinderplus/latest"),
        help="Local database directory",
    )
    args = parser.parse_args()

    print(f"Listing {BASE}")
    files = list_files(BASE)
    if not files:
        raise SystemExit("No files found at AMRFinderPlus latest URL")

    print(f"Found {len(files)} files")
    for name in files:
        download(urljoin(BASE, name), args.out_dir / name)

    (args.out_dir / "SOURCE.txt").write_text(
        f"source={BASE}\nnote=NCBI AMRFinderPlus latest database snapshot\n"
    )
    print("Done.")


if __name__ == "__main__":
    main()
