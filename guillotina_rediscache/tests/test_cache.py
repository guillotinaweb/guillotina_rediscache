from guillotina import app_settings
from guillotina.component import getUtility
from guillotina.tests import mocks
from guillotina.tests.utils import create_content
from guillotina_rediscache import cache
from guillotina_rediscache import serialize
from guillotina_rediscache.cache_strategy import RedisCache
from guillotina_rediscache.interfaces import CACHE_PREFIX
from guillotina_rediscache.interfaces import IRedisChannelUtility

import asyncio


async def test_cache_set(redis_container, dummy_guillotina, loop):
    await cache.close_redis_pool()
    trns = mocks.MockTransaction(mocks.MockTransactionManager())
    trns.added = trns.deleted = {}
    rcache = RedisCache(trns, loop=loop)
    await rcache.clear()

    await rcache.set('bar', oid='foo')
    # make sure it is in redis
    val = await rcache._redis.get(CACHE_PREFIX + 'root-foo')
    assert serialize.loads(val) == "bar"
    # but also in memory
    assert rcache._memory_cache.get('root-foo') == 'bar'
    # and api matches..
    assert await rcache.get(oid='foo') == 'bar'

    await cache.close_redis_pool()


async def test_cache_delete(redis_container, dummy_guillotina, loop):
    await cache.close_redis_pool()
    trns = mocks.MockTransaction(mocks.MockTransactionManager())
    trns.added = trns.deleted = {}
    rcache = RedisCache(trns, loop=loop)
    await rcache.clear()

    await rcache.set('bar', oid='foo')
    # make sure it is in redis
    assert serialize.loads(
        await rcache._redis.get(CACHE_PREFIX + 'root-foo')) == "bar"
    assert rcache._memory_cache.get('root-foo') == 'bar'
    assert await rcache.get(oid='foo') == 'bar'

    # now delete
    await rcache.delete('root-foo')
    assert await rcache.get(oid='foo') is None

    await cache.close_redis_pool()


async def test_cache_clear(redis_container, dummy_guillotina, loop):
    await cache.close_redis_pool()
    trns = mocks.MockTransaction(mocks.MockTransactionManager())
    trns.added = trns.deleted = {}
    rcache = RedisCache(trns, loop=loop)
    await rcache.clear()

    await rcache.set('bar', oid='foo')
    # make sure it is in redis
    assert serialize.loads(
        await rcache._redis.get(CACHE_PREFIX + 'root-foo')) == "bar"
    assert rcache._memory_cache.get('root-foo') == 'bar'
    assert await rcache.get(oid='foo') == 'bar'

    await rcache.clear()
    assert await rcache.get(oid='foo') is None

    await cache.close_redis_pool()


async def test_invalidate_object(redis_container, dummy_guillotina, loop):
    await cache.close_redis_pool()
    trns = mocks.MockTransaction(mocks.MockTransactionManager())
    trns.added = trns.deleted = {}
    content = create_content()
    trns.modified = {content._p_oid: content}
    rcache = RedisCache(trns, loop=loop)
    await rcache.clear()

    await rcache.set('foobar', oid=content._p_oid)
    assert serialize.loads(
        await rcache._redis.get(
            CACHE_PREFIX + 'root-' + content._p_oid)) == "foobar"
    assert rcache._memory_cache.get('root-' + content._p_oid) == 'foobar'
    assert await rcache.get(oid=content._p_oid) == 'foobar'

    await rcache.close(invalidate=True)
    assert await rcache.get(oid=content._p_oid) is None

    await cache.close_redis_pool()


async def test_subscriber_invalidates(redis_container, dummy_guillotina, loop):
    await cache.close_redis_pool()
    trns = mocks.MockTransaction(mocks.MockTransactionManager())
    trns.added = trns.deleted = {}
    content = create_content()
    trns.modified = {content._p_oid: content}
    rcache = RedisCache(trns, loop=loop)
    await rcache.clear()

    await rcache.set('foobar', oid=content._p_oid)
    assert serialize.loads(
        await rcache._redis.get(
            CACHE_PREFIX + 'root-' + content._p_oid)) == "foobar"
    assert rcache._memory_cache.get(
        'root-' + content._p_oid) == 'foobar'
    assert await rcache.get(oid=content._p_oid) == 'foobar'

    assert 'root-' + content._p_oid in rcache._memory_cache

    await rcache._redis.publish(
        app_settings['redis']['updates_channel'], serialize.dumps({
            'tid': 32423,
            'keys': ['root-' + content._p_oid]
        }))
    await asyncio.sleep(1)  # should be enough for pub/sub to finish
    assert 'root-' + content._p_oid not in rcache._memory_cache

    await cache.close_redis_pool()


async def test_subscriber_ignores_trsn_on_invalidate(
        redis_container, dummy_guillotina, loop):
    await cache.close_redis_pool()
    trns = mocks.MockTransaction(mocks.MockTransactionManager())
    trns.added = trns.deleted = {}
    content = create_content()
    trns.modified = {content._p_oid: content}
    rcache = RedisCache(trns, loop=loop)
    await rcache.clear()

    await rcache.set('foobar', oid=content._p_oid)
    assert serialize.loads(
        await rcache._redis.get(
            CACHE_PREFIX + 'root-' + content._p_oid)) == "foobar"
    assert rcache._memory_cache.get('root-' + content._p_oid) == 'foobar'
    assert await rcache.get(oid=content._p_oid) == 'foobar'

    assert 'root-' + content._p_oid in rcache._memory_cache

    utility = getUtility(IRedisChannelUtility)
    utility.ignore_tid(5555)

    await rcache._redis.publish(
        app_settings['redis']['updates_channel'], serialize.dumps({
            'tid': 5555,
            'keys': ['root-' + content._p_oid]
        }))
    await asyncio.sleep(1)  # should be enough for pub/sub to finish
    # should still be there because we set to ignore this tid
    assert 'root-' + content._p_oid in rcache._memory_cache
    # tid should also now be removed from ignored list
    assert 5555 not in utility._ignored_tids

    await cache.close_redis_pool()


async def test_get_size_of_item(dummy_guillotina, loop):
    await cache.close_redis_pool()
    trns = mocks.MockTransaction(mocks.MockTransactionManager())
    trns.added = trns.deleted = {}
    rcache = RedisCache(trns)
    from guillotina_rediscache.cache_strategy import _default_size
    import sys
    assert rcache.get_size(dict(a=1)) == _default_size
    assert rcache.get_size(1) == sys.getsizeof(1)
    assert rcache.get_size(dict(state=b'x'*10)) == 10

    item = [
        'x'*10, 'x'*10, 'x'*10
    ]

    assert rcache.get_size(item) == sys.getsizeof('x'*10) * 3
