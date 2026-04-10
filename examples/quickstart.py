"""Quick Start: Create your first post with UniPost."""

from unipost import UniPost

# Reads UNIPOST_API_KEY from environment automatically
client = UniPost()

# List connected accounts
result = client.accounts.list()
accounts = result["data"]
print(f"Found {len(accounts)} connected accounts")

if not accounts:
    print("Connect an account first at https://app.unipost.dev")
    exit()

# Create a post
post = client.posts.create(
    caption="Hello from UniPost Python SDK! 🚀",
    account_ids=[a.id for a in accounts],
)

print(f"Post created: {post.id} (status: {post.status})")
