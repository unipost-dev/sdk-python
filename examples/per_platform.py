"""Per-platform captions: Different copy for each platform."""

from unipost import UniPost

client = UniPost()

post = client.posts.create(
    platform_posts=[
        {
            "account_id": "sa_twitter_xxx",
            "caption": "Short and punchy for Twitter 🐦",
        },
        {
            "account_id": "sa_linkedin_xxx",
            "caption": (
                "I'm excited to share that we've shipped the UniPost Python SDK "
                "— a unified API client for posting to 7 social platforms.\n\n"
                "#DevTools #SocialMedia"
            ),
        },
        {
            "account_id": "sa_bluesky_xxx",
            "caption": "Just shipped unipost Python SDK 🦋",
        },
    ]
)

print(f"Multi-platform post: {post.id}")
