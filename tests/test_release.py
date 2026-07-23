from pathlib import Path

import unipost
import unipost.async_client as async_client
import unipost.http as http
import unipost.types as types


EXPECTED_INBOX_EXPORTS = {
    "InboxSource",
    "InboxThreadStatus",
    "InboxItem",
    "InboxListResponse",
    "InboxReplyCompleted",
    "InboxReplyReconciling",
    "InboxReplyResult",
    "InboxUnreadCountResult",
    "InboxMarkAllReadResult",
    "InboxMediaContext",
    "XInboxBackfillRequest",
    "InboxSyncError",
    "InboxSyncAccountDetail",
    "InboxSyncResult",
    "XInboxBackfillAccountResult",
    "XInboxBackfillInProgress",
    "XInboxBackfillConfirmationRequired",
    "XInboxBackfillCompleted",
    "XInboxBackfillResult",
    "XInboxOutboundStatus",
    "InboxWebSocketConnectionDetails",
}


def test_release_version_is_consistent() -> None:
    pyproject = Path(__file__).parents[1].joinpath("pyproject.toml").read_text()

    assert 'version = "0.6.0"' in pyproject
    assert unipost.__version__ == "0.6.0"
    assert http.SDK_VERSION == "0.6.0"
    assert async_client.SDK_VERSION == "0.6.0"


def test_top_level_package_exports_complete_inbox_contract() -> None:
    for name in EXPECTED_INBOX_EXPORTS:
        assert getattr(unipost, name, None) is getattr(types, name)
        assert name in unipost.__all__
