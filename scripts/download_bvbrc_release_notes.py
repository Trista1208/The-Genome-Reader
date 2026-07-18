#!/usr/bin/env python3
"""Download BV-BRC RELEASE_NOTES tables via anonymous FTPS.

Primary challenge data source (lab-measured AMR phenotypes + genome metadata).
Docs: https://www.bv-brc.org/docs/quick_references/ftp.html
"""

from __future__ import annotations

import argparse
import hashlib
import ssl
from ftplib import FTP_TLS
from pathlib import Path

HOST = "ftp.bv-brc.org"
REMOTE_DIR = "/RELEASE_NOTES"
FILES = [
    "PATRIC_genomes_AMR.txt",  # lab AMR phenotypes (note plural "genomes")
    "genome_summary",
    "genome_metadata",
    "genome_lineage",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(ftp: FTP_TLS, name: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    size = 0
    if tmp.exists():
        size = tmp.stat().st_size

    # SIZE only works in binary mode on BV-BRC FTPS.
    ftp.voidcmd("TYPE I")
    try:
        remote_size = ftp.size(name)
    except Exception:  # noqa: BLE001
        remote_size = None

    if dest.exists() and remote_size is not None and dest.stat().st_size == remote_size:
        print(f"[skip] {name} already complete ({remote_size:,} bytes)")
        return

    mode = "ab" if size and remote_size and size < remote_size else "wb"
    if mode == "wb" and tmp.exists():
        tmp.unlink()
        size = 0

    print(f"[get]  {name} -> {dest} (resume={size:,})")

    with tmp.open(mode) as out:
        def _write(block: bytes) -> None:
            out.write(block)

        if size:
            ftp.retrbinary(f"RETR {name}", _write, rest=size)
        else:
            ftp.retrbinary(f"RETR {name}", _write)

    tmp.replace(dest)
    digest = sha256_file(dest)
    print(f"[ok]   {name} ({dest.stat().st_size:,} bytes) sha256={digest}")
    (dest.with_suffix(dest.suffix + ".sha256")).write_text(f"{digest}  {dest.name}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/raw/bvbrc/RELEASE_NOTES"),
        help="Local output directory",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=FILES,
        help="RELEASE_NOTES filenames to download",
    )
    args = parser.parse_args()

    ctx = ssl.create_default_context()
    # BV-BRC docs recommend disabling cert verify for some clients.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    print(f"Connecting FTPS anonymous@{HOST}{REMOTE_DIR} ...")
    ftp = FTP_TLS(context=ctx)
    ftp.connect(HOST, 21, timeout=120)
    ftp.login("anonymous", "guest")
    ftp.prot_p()
    ftp.cwd(REMOTE_DIR)
    ftp.set_pasv(True)

    for name in args.files:
        download_file(ftp, name, args.out_dir / name)

    ftp.quit()
    print("Done.")


if __name__ == "__main__":
    main()
