#!/usr/bin/env python3
"""Download BV-BRC assembled FASTA (.fna) files for a genome_list via FTPS.

Example:
  python scripts/download_bvbrc_genomes.py \\
    --genome-list data/processed/cohort/genome_list.txt \\
    --out-dir data/raw/bvbrc/genomes
"""

from __future__ import annotations

import argparse
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from ftplib import FTP_TLS, error_perm
from pathlib import Path

HOST = "ftp.bv-brc.org"


def connect() -> FTP_TLS:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ftp = FTP_TLS(context=ctx)
    ftp.connect(HOST, 21, timeout=180)
    ftp.login("anonymous", "guest")
    ftp.prot_p()
    ftp.set_pasv(True)
    return ftp


def download_one(genome_id: str, out_dir: Path, retries: int = 3) -> tuple[str, str]:
    dest = out_dir / f"{genome_id}.fna"
    if dest.exists() and dest.stat().st_size > 0:
        return genome_id, "skip"

    remote = f"/genomes/{genome_id}/{genome_id}.fna"
    tmp = dest.with_suffix(".fna.partial")
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            ftp = connect()
            with tmp.open("wb") as out:
                ftp.retrbinary(f"RETR {remote}", out.write)
            ftp.quit()
            if tmp.stat().st_size == 0:
                tmp.unlink(missing_ok=True)
                return genome_id, "empty"
            tmp.replace(dest)
            return genome_id, "ok"
        except error_perm as e:
            last_err = str(e)
            tmp.unlink(missing_ok=True)
            return genome_id, f"missing:{e}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            tmp.unlink(missing_ok=True)
            time.sleep(1.5 * attempt)
    return genome_id, f"fail:{last_err}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--genome-list",
        type=Path,
        default=Path("data/processed/cohort/genome_list.txt"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/raw/bvbrc/genomes"),
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Optional cap for smoke tests")
    args = parser.parse_args()

    ids = [
        line.strip()
        for line in args.genome_list.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if args.limit:
        ids = ids[: args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(ids):,} genomes -> {args.out_dir} (workers={args.workers})")

    ok = skip = fail = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(download_one, gid, args.out_dir): gid for gid in ids}
        for i, fut in enumerate(as_completed(futures), 1):
            gid, status = fut.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
                print(f"[warn] {gid}: {status}")
            if i % 25 == 0 or i == len(ids):
                print(f"[{i}/{len(ids)}] ok={ok} skip={skip} fail={fail}")

    print(f"Done. ok={ok} skip={skip} fail={fail}")


if __name__ == "__main__":
    main()
