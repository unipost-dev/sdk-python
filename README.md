# unipost

Official UniPost API client for Python.
Post to 7 social platforms with one API call.

## Latest release: v0.5.0

Media uploads now support custom audio overlay jobs and optional reserve-time file sizes.

- Use `client.media.audio_overlays.create(...)` to combine one uploaded video with one uploaded audio file.
- Poll the job with `client.media.audio_overlays.get(...)`, then publish the returned `output_media_id`.
- Omit `size_bytes` when reserving media if your app cannot know the raw file length up front.
- Post failure responses also include the typed v0.4.1 error contract fields.

Supported analytics surfaces include Instagram, Threads, Pinterest, and TikTok when connected account permissions allow them. See `Analytics Explorer` below for code.

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

### Analytics Explorer

```python
posts = client.analytics.posts(
    platform="tiktok",
    limit=25,
    sort="engagement_rate",
)

platforms = client.analytics.platforms()
tiktok = client.analytics.platform("tiktok")
csv = client.analytics.export_posts_csv(platform="pinterest")

client.analytics.refresh(
    platform="threads",
    limit=100,
)
```

### Developer Logs

```python
page = client.logs.list(status="error", limit=50)

if page["data"]:
    log = client.logs.get(page["data"][0]["id"])
    print(log["action"], log.get("request_payload"))

for log in client.logs.stream(status="error", after_id=page["data"][0]["id"] if page["data"] else 0):
    print(log["id"], log["action"])
    break
```

### Media Upload

```python
reserved = client.media.upload(
    filename="voiceover.mp3",
    content_type="audio/mpeg",
    # size_bytes is optional; upload_file calculates it automatically
)
```

### Custom Audio Overlay

```python
from time import sleep

job = client.media.audio_overlays.create(
    video_media_id="media_video_123",
    audio_media_id="media_audio_456",
    mode="mix",
    video_volume=70,
    audio_volume=100,
    fit="trim_to_video",
    idempotency_key="overlay-demo-001",
)

while job.status in ("queued", "processing"):
    sleep(1.5)
    job = client.media.audio_overlays.get(job.id)

if job.status != "succeeded":
    raise RuntimeError(job.error.message if job.error else "audio overlay failed")

client.posts.create(
    caption="Video with custom audio",
    account_ids=["sa_tiktok_xxx"],
    media_ids=[job.output_media_id],
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

### Connect (Managed Users)

```python
session = client.connect.create_session(
    platform="twitter",
    external_user_id="your_user_123",
    return_url="https://yourapp.com/callback",
    allow_quickstart_creds=True,  # optional
)

print(session.url)
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
