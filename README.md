# unipost

Official UniPost API client for Python.
Post to 7 social platforms with one API call.

## Latest release: v0.6.0

Scoped Inbox support is now available for server-side applications.

- Bind every Inbox operation to either `client.inbox.managed_user(id)` or `client.inbox.workspace()`.
- List, read, reply, thread state, media context, sync, X backfill, X reply reconciliation, and WebSocket connection details are typed for sync and async clients.
- X replies distinguish completed delivery from accepted-but-reconciling delivery.
- WebSocket helpers return connection details without opening a connection or adding a production dependency.

See the [changelog](CHANGELOG.md) for the complete release history.

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

### Inbox (server-side apps)

Keep the workspace API key on your application backend. Never expose it to managed users, browser code, or a mobile app. Derive the external user ID from your authenticated application session—not an arbitrary scope value supplied by the caller—and bind every managed-user operation with `client.inbox.managed_user(id)`. Managed-user scope never falls back to workspace scope. Reserve `client.inbox.workspace()` for authenticated app owners and admins who are allowed to use an aggregate Inbox.

Create the scoped resources on your backend:

```python
from unipost import UniPost


def inbox_scopes(workspace_api_key: str, authenticated_external_user_id: str):
    client = UniPost(api_key=workspace_api_key)
    return {
        "managed": client.inbox.managed_user(authenticated_external_user_id),
        "owner_admin": client.inbox.workspace(),
    }
```

The selected scope is carried by every Inbox request. Listing accepts `source`, `is_read`, `is_own`, and `limit`; explicit `False` values are preserved. It is limit-only and returns one non-paginated page. The server default is 50 items and the server clamps the limit to 500.

```python
inbox = inbox_scopes(workspace_api_key, authenticated_external_user_id)["managed"]

page = inbox.list(source="x_dm", is_read=False, is_own=False, limit=25)
unread = inbox.unread_count()

if page.data:
    item = inbox.get(page.data[0].id)
    inbox.mark_read(item.id)
    item = inbox.update_thread_state(
        item.id,
        thread_status="assigned",
        assigned_to="owner_123",
    )
    media = inbox.media_context(item.id)

marked = inbox.mark_all_read()
```

Replies are response-aware. A `completed` result contains the reply item. A `reconciling` result means X accepted the reply while UniPost is still reconciling it. Generate one stable idempotency key per logical X reply, reuse that same key for transport retries, and poll `x_outbound_status(...)` when reconciliation is required. Never resend a reconciling reply under a new key.

```python
item_id = "inbox_item_from_scoped_list"
result = inbox.reply(
    item_id,
    text="Thanks—we are looking into this.",
    idempotency_key="reply_01JSTABLEKEY",
)

if result.state == "completed":
    print(result.item.id)
else:
    status = inbox.x_outbound_status(result.operation_id)
    print(status.status)
```

`websocket_connection_details()` is backend-only and does not open a connection. It returns a URL plus the API key only in the `Authorization` header. Pass those details to a server-side WebSocket client that supports custom headers; never log the header or put the key in the URL. Native browser WebSocket clients cannot set the required authorization header.

```python
details = inbox.websocket_connection_details()
# Connect from your backend with details.url and details.headers.
```

Calling `sync()` without arguments performs ordinary polling for the selected scope. Passing `x_backfill` requests metered X history. Managed-user scope narrows eligible accounts, while workspace scope can span every eligible managed user and account in the workspace. Inspect the estimate and confirmation response, review its scope and X credit cost, then repeat the exact request with the returned confirmation token. Treat the token as a secret: do not log it, send it to a browser, or store it in client-visible state. Never schedule an unreviewed workspace-wide X backfill.

```python
from unipost import XInboxBackfillRequest

ordinary = inbox.sync()

request = XInboxBackfillRequest(
    account_id="sa_x_123",
    lookback_days=7,
    max_items=100,
    include_replies=True,
    include_dms=False,
)
estimate = inbox.sync(x_backfill=request)

if estimate.confirmation_required:
    confirmed = inbox.sync(
        x_backfill=XInboxBackfillRequest(
            account_id=request.account_id,
            lookback_days=request.lookback_days,
            max_items=request.max_items,
            include_replies=request.include_replies,
            include_dms=request.include_dms,
            confirmation_token=estimate.confirmation_token,
        )
    )
    print(confirmed)
```

The async client exposes the same scopes and contract. Await network operations; `websocket_connection_details()` remains synchronous because it only prepares immutable connection details.

```python
from unipost import AsyncUniPost


async def handle_inbox(workspace_api_key: str, external_user_id: str) -> None:
    client = AsyncUniPost(api_key=workspace_api_key)
    inbox = client.inbox.managed_user(external_user_id)

    page = await inbox.list(is_read=False, limit=25)
    unread = await inbox.unread_count()
    if page.data:
        await inbox.mark_read(page.data[0].id)
    ordinary = await inbox.sync()
    details = inbox.websocket_connection_details()
    print(unread.count, ordinary.new_items, details.url)
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
