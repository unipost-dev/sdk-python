# unipost

Official UniPost API client for Python.
Post to 7 social platforms with one API call.

## Installation

```bash
pip install unipost
```

For async support:

```bash
pip install unipost[async]
```

## Quick Start

```python
from unipost import UniPost

# Reads UNIPOST_API_KEY from environment automatically
client = UniPost()

post = client.posts.create(
    caption="Hello from UniPost! 🚀",
    account_ids=["sa_twitter_xxx", "sa_linkedin_xxx"],
)
```

## Usage

### List Accounts

```python
result = client.accounts.list()
accounts = result["data"]

# Filter by platform
twitter = client.accounts.list(platform="twitter")
```

### Create Posts

```python
# Immediate publish
post = client.posts.create(
    caption="Hello world!",
    account_ids=["sa_twitter_xxx"],
)

# Scheduled
post = client.posts.create(
    caption="Scheduled post",
    account_ids=["sa_twitter_xxx"],
    scheduled_at="2026-04-28T09:00:00Z",
)

# Per-platform captions
post = client.posts.create(
    platform_posts=[
        {"account_id": "sa_twitter_xxx", "caption": "Short tweet 🐦"},
        {"account_id": "sa_linkedin_xxx", "caption": "Longer LinkedIn version..."},
    ]
)

# Save as draft
draft = client.posts.create(
    caption="Work in progress",
    account_ids=["sa_twitter_xxx"],
    status="draft",
)
```

### Async

```python
from unipost import AsyncUniPost

async def main():
    client = AsyncUniPost()
    post = await client.posts.create(
        caption="Async post!",
        account_ids=["sa_twitter_xxx"],
    )
```

### Get Connect URL (Your Own Accounts)

```python
connect = client.connect.get_connect_url(
    profile_id="pr_brand_us",
    platform="linkedin",
    redirect_url="https://app.acme.com/integrations/done",  # optional
)

print(connect.auth_url)
```

### Webhook Verification

```python
from unipost import verify_webhook_signature

is_valid = verify_webhook_signature(
    payload=request.body,
    signature=request.headers["X-UniPost-Signature"],
    secret=os.environ["UNIPOST_WEBHOOK_SECRET"],
)
```

## Error Handling

```python
from unipost import UniPost, AuthError, RateLimitError, UniPostError

try:
    post = client.posts.create(...)
except AuthError:
    print("API key invalid")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except UniPostError as e:
    print(f"API error: {e.status} {e.code} {e}")
```

## Type Hints

Full type annotations included. Works with mypy.

```python
from unipost import Post, SocialAccount
```

## License

MIT
