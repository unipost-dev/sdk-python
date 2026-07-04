import os
import pytest
from unipost import UniPost, AsyncUniPost


def test_requires_api_key():
    # Ensure env var is not set
    key = os.environ.pop("UNIPOST_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="API key is required"):
            UniPost()
    finally:
        if key:
            os.environ["UNIPOST_API_KEY"] = key


def test_accepts_explicit_api_key():
    client = UniPost(api_key="up_test_xxx")
    assert client.posts is not None
    assert client.accounts is not None
    assert client.media is not None
    assert client.analytics is not None
    assert client.connect is not None
    assert client.users is not None
    assert client.logs is not None


def test_async_requires_api_key():
    key = os.environ.pop("UNIPOST_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="API key is required"):
            AsyncUniPost()
    finally:
        if key:
            os.environ["UNIPOST_API_KEY"] = key


def test_async_accepts_explicit_api_key():
    client = AsyncUniPost(api_key="up_test_xxx")
    assert client.posts is not None
    assert client.accounts is not None
    assert client.media is not None
    assert client.logs is not None
