"""Retry explicit service rejections within the caller's existing deadline."""

import asyncio
import random
from contextlib import asynccontextmanager


@asynccontextmanager
async def service_stream(client, method, url, **kwargs):
    # Never replay timeouts, dropped connections or partial successful responses:
    # the provider may have already generated (and charged for) the result.
    for attempt in range(3):
        async with client.stream(method, url, **kwargs) as response:
            if response.status_code != 503 or attempt == 2:
                yield response
                return
        # Release the failed response before waiting. The caller owns the total
        # timeout, so retries cannot extend a worker lease indefinitely.
        await asyncio.sleep(2 ** (attempt + 1) + random.uniform(0, 1))
