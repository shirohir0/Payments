"""Audited manual resolution after an operator verifies the provider's outcome."""

import argparse
import asyncio
import json

from sqlalchemy import select

from app.core.logging import setup_logging
from app.infrastructure.db.models.outbox import OutboxEvent
from app.infrastructure.db.models.payment import PaymentModel
from app.infrastructure.db.session import AsyncSessionLocal, engine
from app.workers.payment_processor import PaymentProcessor


async def execute(args):
    try:
        if args.command == "reconcile":
            if not args.confirm_provider_outcome:
                raise ValueError(
                    "Verify the provider outcome, then pass --confirm-provider-outcome"
                )
            result = await PaymentProcessor().resolve(args.payment_id, args.outcome, args.reference)
            print(json.dumps({"payment_id": args.payment_id, "status": result}))
        else:
            async with AsyncSessionLocal() as session:
                payment = await session.get(PaymentModel, args.payment_id)
                if payment is None:
                    raise ValueError("Payment not found")
                event = await session.scalar(
                    select(OutboxEvent).where(OutboxEvent.payment_id == payment.id)
                )
                print(
                    json.dumps(
                        {
                            "payment_id": payment.id,
                            "status": payment.status.value,
                            "operation": payment.operation,
                            "amount": str(payment.amount),
                            "commission": str(payment.commission),
                            "funds_reserved": payment.funds_reserved,
                            "attempts": payment.attempts,
                            "last_error": payment.last_error,
                            "requires_reconciliation": bool(
                                event
                                and event.completed_at
                                and (event.last_error or "").startswith("reconciliation_required:")
                            ),
                        }
                    )
                )
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Inspect the current payment state")
    inspect.add_argument("--payment-id", type=int, required=True)
    reconcile = sub.add_parser(
        "reconcile", help="Record a verified provider outcome without charging again"
    )
    reconcile.add_argument("--payment-id", type=int, required=True)
    reconcile.add_argument("--outcome", choices=["success", "failed"], required=True)
    reconcile.add_argument(
        "--reference", required=True, help="Provider receipt or reconciliation ticket"
    )
    reconcile.add_argument("--confirm-provider-outcome", action="store_true")
    args = parser.parse_args()
    if args.payment_id < 1:
        parser.error("Payment ID must be positive")
    setup_logging()
    try:
        asyncio.run(execute(args))
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
