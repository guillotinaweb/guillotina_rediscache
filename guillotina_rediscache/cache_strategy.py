from guillotina import app_settings
from guillotina import configure
from guillotina.component import getUtility
from guillotina.db.cache.base import BaseCache
from guillotina.db.interfaces import IStorageCache
from guillotina.db.interfaces import ITransaction
from guillotina.profile import profilable
from guillotina_rediscache import cache
from guillotina_rediscache import serialize
from guillotina_rediscache.interfaces import CACHE_PREFIX
from guillotina_rediscache.interfaces import IRedisChannelUtility
from sys import getsizeof

import aioredis
import asyncio
import logging


logger = logging.getLogger('guillotina_rediscache')

_default_size = 1024
_basic_types = (bytes, str, int, float)


@configure.adapter(for_=ITransaction, provides=IStorageCache,
                   name="redis")
class RedisCache(BaseCache):
    max_publish_objects = 20

    def __init__(self, transaction, loop=None):
        super().__init__(transaction)
        self._loop = loop

        self._conn = None
        self._redis = None
        self._memory_cache = cache.get_memory_cache()
        self._settings = app_settings.get('redis', {})

        self._keys_to_publish = []

        self._stored_objects = []

    async def get_conn(self):
        if self._conn is None:
            self._conn = await cache.get_redis_pool(self._loop)
        return self._conn

    async def get_redis(self):
        if self._redis is None:
            self._redis = aioredis.Redis(await self.get_conn())
        return self._redis

    @profilable
    async def get(self, **kwargs):
        key = self.get_key(**kwargs)
        try:
            if key in self._memory_cache:
                logger.info('Retrieved {} from memory cache'.format(key))
                return self._memory_cache[key]
            conn = await self.get_redis()
            val = await conn.get(CACHE_PREFIX + key)
            if val is not None:
                logger.info('Retrieved {} from redis cache'.format(key))
                val = serialize.loads(val)
                self._memory_cache[key] = val
            return val
        except Exception:
            logger.warning('Error getting cache value', exc_info=True)

    @profilable
    async def set(self, value, **kwargs):
        key = self.get_key(**kwargs)
        try:
            conn = await self.get_redis()

            size = self.get_size(value)
            self._memory_cache.set(key, value, size)
            await conn.set(CACHE_PREFIX + key, serialize.dumps(value),
                           expire=self._settings.get('ttl', 3600))
            logger.info('set {} in cache'.format(key))
        except Exception:
            logger.warning('Error setting cache value', exc_info=True)

    def get_size(self, value):
        if isinstance(value, dict):
            if 'state' in value:
                return len(value['state'])
        if isinstance(value, list) and len(value) > 0:
            # if its a list, guesss from first gey the length, and
            # estimate it from the total lenghts on the list..
            return getsizeof(value[0]) * len(value)
        if type(value) in _basic_types:
            return getsizeof(value)
        return _default_size

    @profilable
    async def clear(self):
        try:
            self._memory_cache.clear()
            conn = await self.get_redis()
            await conn.flushall()
            logger.info('Cleared cache')
        except Exception:
            logger.warning('Error clearing cache', exc_info=True)

    @profilable
    async def delete(self, key):
        await self.delete_all([key])

    @profilable
    async def delete_all(self, keys):
        delete_keys = []
        for key in keys:
            self._keys_to_publish.append(key)
            delete_keys.append(CACHE_PREFIX + key)
            if key in self._memory_cache:
                del self._memory_cache[key]
        if len(delete_keys) > 0:
            try:
                conn = await self.get_redis()
                if self._settings.get('cluster_mode', False):
                    for key in delete_keys:
                        await conn.delete(key)
                else:
                    await conn.delete(*delete_keys)
                logger.info('Deleted cache keys {}'.format(delete_keys))
            except Exception:
                logger.warning('Error deleting cache keys {}'.format(
                    delete_keys), exc_info=True)

    async def store_object(self, obj, pickled):
        if len(self._stored_objects) < self.max_publish_objects:
            self._stored_objects.append((obj, pickled))
            # also assume these objects are then stored
            # (even though it's done after the request)
            self._stored += 1

    @profilable
    async def _invalidate_keys(self, groups):
        invalidated = []
        for data, type_ in groups:
            for oid, ob in data.items():
                invalidated.extend(self.get_cache_keys(ob, type_))
        await self.delete_all(invalidated)
        return invalidated

    @profilable
    async def close(self, invalidate=True):
        try:
            if self._conn is None:
                if not invalidate:
                    # skip out, nothing to do
                    return
                await self.get_redis()  # force getting connnection object

            if invalidate:
                await self._invalidate_keys([
                    (self._transaction.modified, 'modified'),
                    (self._transaction.added, 'added'),
                    (self._transaction.deleted, 'deleted')
                ])

            if len(self._keys_to_publish) > 0:
                asyncio.ensure_future(self._synchronize(
                    self._stored_objects, self._keys_to_publish,
                    self._transaction._tid))
            self._keys_to_publish = []
            self._stored_objects = []
        except Exception:
            logger.warning('Error closing connection', exc_info=True)

    @profilable
    async def _synchronize(self, stored_objects, keys_to_publish, tid):
        '''
        publish cache changes on redis
        '''
        push = {}
        for obj, pickled in stored_objects:
            val = {
                'state': pickled,
                'zoid': obj._p_oid,
                'tid': obj._p_serial,
                'id': obj.__name__
            }
            if obj.__of__:
                ob_key = self.get_key(
                    oid=obj.__of__, id=obj.__name__, variant='annotation')
                await self.set(
                    val, oid=obj.__of__, id=obj.__name__, variant='annotation')
            else:
                ob_key = self.get_key(
                    container=obj.__parent__, id=obj.__name__)
                await self.set(
                    val, container=obj.__parent__, id=obj.__name__)

            if ob_key in keys_to_publish:
                keys_to_publish.remove(ob_key)
            push[ob_key] = val

        channel_utility = getUtility(IRedisChannelUtility)
        channel_utility.ignore_tid(tid)
        await self._redis.publish(
            self._settings['updates_channel'], serialize.dumps({
                'tid': tid,
                'keys': keys_to_publish,
                'push': push
            }))
