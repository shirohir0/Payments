"""Restore a PostgreSQL backup to a NEW database; never overwrite an existing one."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--database", required=True, help="New PostgreSQL database name")
    parser.add_argument("--project", default="payments")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", args.database) or args.database in {
        "postgres",
        "template0",
        "template1",
    }:
        parser.error("Use a new lowercase database name, 1..63 letters/digits/underscores.")
    backup = args.backup.resolve(strict=True)
    checksum = backup.with_suffix(backup.suffix + ".sha256")
    if checksum.exists():
        expected = checksum.read_text(encoding="utf-8").split()[0]
        with backup.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if expected != actual:
            parser.error("Backup checksum does not match; restore was not started.")
    root = Path(__file__).resolve().parents[1]
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
    ]
    create = subprocess.run(
        command + ['exec createdb --username="$POSTGRES_USER" "$1"', "sh", args.database],
        cwd=root,
        check=False,
    )
    if create.returncode:
        print(
            "New database could not be created. Existing databases were not modified.",
            file=sys.stderr,
        )
        return create.returncode
    with backup.open("rb") as source:
        restore = subprocess.run(
            command
            + [
                'exec pg_restore --username="$POSTGRES_USER" --dbname="$1" --no-owner --no-acl --exit-on-error --single-transaction',
                "sh",
                args.database,
            ],
            cwd=root,
            stdin=source,
            check=False,
        )
    if restore.returncode:
        print(
            "Restore failed. The new database remains for inspection; restore transaction was rolled back.",
            file=sys.stderr,
        )
        return restore.returncode
    print(
        f"Restored into new database: {args.database}. Validate it before changing application connections."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
