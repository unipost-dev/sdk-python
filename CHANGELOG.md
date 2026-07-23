# Changelog

## 0.6.0 (2026-07-22)

- Add explicit managed-user and workspace Inbox scopes with no implicit workspace fallback.
- Cover Inbox listing, unread counts, item reads, read state, thread state, media context, replies, sync, and X outbound status for sync and async clients.
- Return typed completed or reconciling reply states for safe X reply idempotency and reconciliation.
- Provide backend WebSocket connection details without opening a connection or adding a mandatory dependency.
- Add typed ordinary Inbox sync plus metered X backfill estimation, confirmation, account results, and outbound operation status.

## 0.5.0 (2026-07-03)

- Add custom audio overlay jobs and optional reserve-time media file sizes.
- Include the typed post failure error contract fields.
