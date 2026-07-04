"""Create a PostgreSQL custom-format backup without shell/binary redirection."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="payments", help="Running Compose project name")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (
        args.output or root / "backups" / f"payments-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.dump"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "docker",
        "compose",
        "--project-name",
        args.project,
        "--env-file",
        str(Path(args.env_file).resolve()),
        "-f",
        str(root / "docker-compose.yml"),
        "exec",
        "-T",
        "db",
        "sh",
        "-ec",
        'exec pg_dump --format=custom --no-owner --no-acl --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"',
    ]
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            result = subprocess.run(
                command, cwd=root, stdout=destination, stderr=subprocess.PIPE, check=False
            )
        if result.returncode:
            output.unlink()
            print("Backup failed; no completed backup was saved.", file=sys.stderr)
            print(result.stderr.decode(errors="replace")[-2000:], file=sys.stderr)
            return result.returncode
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    with output.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    with checksum.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {output.name}\n")
    print(f"Backup: {output}")
    print(f"SHA256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
