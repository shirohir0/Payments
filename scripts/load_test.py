"""Bounded end-to-end exercise against a disposable local development instance."""

import argparse
import asyncio
import json
import os
from collections import Counter
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

import httpx


def percentile(values, percentage):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentage)))]


async def run(args):
    hostname = urlsplit(args.base_url).hostname
    if hostname not in {"localhost", "127.0.0.1", "::1"} and not args.allow_remote:
        raise ValueError("Use a disposable localhost instance or explicitly pass --allow-remote")
    key = os.environ.get("API_KEY")
    if not key:
        raise ValueError("Set API_KEY in the process environment")
    run_id = uuid4().hex
    headers = {"X-API-Key": key}
    limits = httpx.Limits(
        max_connections=args.concurrency, max_keepalive_connections=args.concurrency
    )
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), headers=headers, timeout=30, limits=limits
    ) as client:
        users = []
        for _ in range(args.accounts):
            response = await client.post("/api/v1/users/", json={"balance": "0.00"})
            response.raise_for_status()
            users.append(response.json()["id"])
        latencies, payment_ids, errors = [], {}, []
        expected = Counter()
        semaphore = asyncio.Semaphore(args.concurrency)

        async def submit(index):
            async with semaphore:
                user_id = users[index % len(users)]
                started = perf_counter()
                response = await client.post(
                    "/api/v1/payments/deposit",
                    headers={"Idempotency-Key": f"load-{run_id}-{index}"},
                    json={"user_id": user_id, "deposit": "1.00"},
                )
                latencies.append(perf_counter() - started)
                if response.status_code != 202:
                    errors.append({"index": index, "http_status": response.status_code})
                    return
                payment_id = response.json()["payment_id"]
                payment_ids[payment_id] = user_id
                expected[user_id] += 1
                if index % 10 == 0:
                    replay = await client.post(
                        "/api/v1/payments/deposit",
                        headers={"Idempotency-Key": f"load-{run_id}-{index}"},
                        json={"user_id": user_id, "deposit": "1.00"},
                    )
                    if replay.status_code != 202 or replay.json().get("payment_id") != payment_id:
                        errors.append({"index": index, "error": "idempotency_replay_mismatch"})

        started = perf_counter()
        await asyncio.gather(*(submit(i) for i in range(args.requests)))
        acceptance_seconds = perf_counter() - started
        pending = set(payment_ids)
        succeeded = 0
        deadline = started + args.timeout
        while pending and perf_counter() < deadline:

            async def inspect(payment_id):
                async with semaphore:
                    response = await client.get(f"/api/v1/payments/{payment_id}")
                    response.raise_for_status()
                    return payment_id, response.json()["status"]

            for payment_id, status in await asyncio.gather(*(inspect(i) for i in pending)):
                if status in {"success", "failed"}:
                    pending.remove(payment_id)
                    if status == "success":
                        succeeded += 1
                    else:
                        errors.append({"payment_id": payment_id, "error": "payment_failed"})
            if pending:
                await asyncio.sleep(0.25)
        elapsed = perf_counter() - started
        accounting_errors = []
        if not pending:
            for user_id, count in expected.items():
                response = await client.get(f"/api/v1/users/{user_id}")
                response.raise_for_status()
                data = response.json()
                if (
                    Decimal(data["balance"]) != Decimal("0.98") * count
                    or Decimal(data["reserved_balance"]) != 0
                ):
                    accounting_errors.append(
                        {"user_id": user_id, "error": "unexpected_balance_or_reservation"}
                    )
        report = {
            "requests": args.requests,
            "accounts": args.accounts,
            "concurrency": args.concurrency,
            "accepted": len(payment_ids),
            "completed_successfully": succeeded,
            "pending": len(pending),
            "acceptance_seconds": round(acceptance_seconds, 3),
            "end_to_end_seconds": round(elapsed, 3),
            "accepted_per_second": round(len(payment_ids) / acceptance_seconds, 2),
            "completed_per_second": round(succeeded / elapsed, 2),
            "request_latency_ms": {
                f"p{int(p * 100)}": round(percentile(latencies, p) * 1000, 2)
                for p in (0.5, 0.95, 0.99)
            },
            "request_errors": errors,
            "accounting_errors": accounting_errors,
        }
        content = json.dumps(report, indent=2)
        print(content)
        if args.output:
            Path(args.output).write_text(content + "\n", encoding="utf-8")
        if errors or accounting_errors or pending:
            raise RuntimeError("The end-to-end exercise did not meet all accounting checks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--accounts", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    if min(args.requests, args.accounts, args.concurrency) < 1 or args.timeout <= 0:
        parser.error("Counts, concurrency and timeout must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
