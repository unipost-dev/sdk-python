import hashlib
import hmac
from unipost.webhook import verify_webhook_signature


def test_valid_signature():
    secret = "whsec_test"
    payload = '{"event":"post.published"}'
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload=payload, signature=sig, secret=secret) is True


def test_invalid_signature():
    assert verify_webhook_signature(
        payload='{"event":"post.published"}',
        signature="0" * 64,
        secret="whsec_test",
    ) is False
