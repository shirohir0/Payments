from app.workers.celery_app import celery_app


def enqueue_payment(payment_id: int) -> None:
    celery_app.send_task("payments.process", args=[payment_id])
