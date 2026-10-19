import asyncio
import pytest

from app.runner import JobBroadcaster


@pytest.mark.asyncio
async def test_publish_reaches_subscriber():
    loop = asyncio.get_running_loop()
    b = JobBroadcaster(loop)
    q = await b.subscribe(1)
    b.publish(1, "hello\n")
    item = await asyncio.wait_for(q.get(), timeout=1)
    assert item == "hello\n"


@pytest.mark.asyncio
async def test_close_sends_sentinel():
    loop = asyncio.get_running_loop()
    b = JobBroadcaster(loop)
    q = await b.subscribe(2)
    b.close(2)
    item = await asyncio.wait_for(q.get(), timeout=1)
    assert item is None
