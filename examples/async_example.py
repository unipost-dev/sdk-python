"""Async usage with AsyncUniPost (requires httpx)."""

import asyncio
from unipost import AsyncUniPost


async def main():
    client = AsyncUniPost()

    # List accounts
    result = await client.accounts.list()
    accounts = result["data"]
    print(f"Found {len(accounts)} accounts")

    if accounts:
        # Create a post
        post = await client.posts.create(
            caption="Async post from Python! 🐍",
            account_ids=[accounts[0].id],
        )
        print(f"Post: {post.id} ({post.status})")


asyncio.run(main())
