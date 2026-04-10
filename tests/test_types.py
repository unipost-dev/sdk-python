from unipost.types import SocialAccount, Post, _from_dict


def test_social_account_from_dict():
    data = {
        "id": "sa_1",
        "platform": "twitter",
        "account_name": "unipost",
        "status": "active",
        "connected_at": "2026-04-09T00:00:00Z",
        "connection_type": "byo",
        "unknown_field": "ignored",
    }
    account = _from_dict(SocialAccount, data)
    assert account.id == "sa_1"
    assert account.platform == "twitter"
    assert account.account_name == "unipost"


def test_post_from_dict():
    data = {
        "id": "post_1",
        "caption": "Hello",
        "status": "published",
        "created_at": "2026-04-09T00:00:00Z",
    }
    post = _from_dict(Post, data)
    assert post.id == "post_1"
    assert post.caption == "Hello"
    assert post.results == []
