import asyncio
from app.rate_limiter import TokenBucket, LeakyBucket

def test_token_bucket():
    async def run():
        b=TokenBucket(2,0)
        assert await b.allow("x")
        assert await b.allow("x")
        assert not await b.allow("x")
    asyncio.run(run())

def test_leaky_bucket():
    async def run():
        b=LeakyBucket(2,0)
        assert await b.allow("x")
        assert await b.allow("x")
        assert not await b.allow("x")
    asyncio.run(run())
