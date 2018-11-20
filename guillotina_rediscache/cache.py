from guillotina import app_settings
from guillotina_rediscache.lru import LRU

import aioredis


_redis_pool = None
_lru = None


async def close_redis_pool():
    global _redis_pool
    if _redis_pool is not None:
        try:
            await _redis_pool.clear()
        except RuntimeError:
            pass
        _redis_pool = None


async def get_redis_pool(loop=None):
    global _redis_pool
    if _redis_pool is None:
        settings = app_settings['redis']
        _redis_pool = await aioredis.create_pool(
            (settings['host'], settings['port']),
            **settings['pool'],
            loop=loop)
    return _redis_pool


def get_memory_cache():
    global _lru
    if _lru is None:
        settings = app_settings.get('redis', {
            'memory_cache_size': 209715200
        })
        _lru = LRU(settings['memory_cache_size'])
    return _lru
