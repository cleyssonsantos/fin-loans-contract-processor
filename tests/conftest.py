import pytest
from fakeredis import FakeAsyncRedis


@pytest.fixture
async def fake_redis():
    r = FakeAsyncRedis()
    yield r
    await r.aclose()
