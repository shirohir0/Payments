class PaymentError(Exception):
    """Base payment error."""


class NotFoundError(PaymentError):
    """Raised when an entity is not found."""


class GatewayError(PaymentError):
    """Raised when payment gateway fails."""
