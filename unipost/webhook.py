"""Webhook signature verification."""

from __future__ import annotations
import hashlib
import hmac


def verify_webhook_signature(
    *,
    payload: str | bytes,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify the HMAC-SHA256 signature of a UniPost webhook request.

    Args:
        payload: The raw request body (str or bytes).
        signature: The value of the X-UniPost-Signature header.
        secret: Your webhook secret.

    Returns:
        True if the signature is valid.
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
