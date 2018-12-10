from guillotina import configure
from guillotina.interfaces import IContainer
from guillotina_rediscache import cache

import aioredis


@configure.service(context=IContainer, name='@redis-cache-stats', method='GET',
                   permission='guillotina_rediscache.Manage')
async def stats(context, request):
    memory_cache = cache.get_memory_cache()

    redis = aioredis.Redis(await cache.get_redis_pool())
    redis_data = await redis.info()
    return {
        'in-memory': {
            'size': len(memory_cache),
            'stats': memory_cache.get_stats()
        },
        'redis': redis_data
    }


@configure.service(context=IContainer, name='@redis-cache-clear', method='POST',
                   permission='guillotina_rediscache.Manage')
async def clear(context, request):
    memory_cache = cache.get_memory_cache()
    memory_cache.clear()
    redis = aioredis.Redis(await cache.get_redis_pool())
    await redis.flushall()
    return {
        'success': True
    }
