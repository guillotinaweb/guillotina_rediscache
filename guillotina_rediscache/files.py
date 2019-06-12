from guillotina.files.adapter import DBDataManager
from guillotina.renderers import GuillotinaJSONEncoder
from guillotina.transactions import get_transaction
from guillotina_rediscache import cache

import aioredis
import json
import time


class RedisFileDataManager(DBDataManager):

    _redis = None
    _data = None
    _loaded = False
    _ttl = 60 * 50 * 5  # 5 minutes should be plenty of time between activity

    async def load(self):
        # preload data
        if self._data is None:
            redis = await self.get_redis()
            key = self.get_key()
            data = await redis.get(key)
            if not data:
                self._data = {}
            else:
                self._loaded = True
                self._data = json.loads(data)

    async def start(self):
        self.protect()
        self._data.clear()

    async def save(self):
        txn = get_transaction(self.request)
        txn.add_after_commit_hook(self._save)

    async def _save(self):
        redis = await self.get_redis()
        key = self.get_key()
        self._data['last_activity'] = time.time()
        await redis.set(
            key, json.dumps(self._data, cls=GuillotinaJSONEncoder),
            expire=self._ttl)

    async def get_redis(self):
        if self._redis is None:
            conn = await cache.get_redis_pool()
            self._redis = aioredis.Redis(conn)
        return self._redis

    def get_key(self):
        # only need 1 write to save upload object id...
        return '{}-{}'.format(
            self.context._p_oid,
            self.field.__name__
        )

    async def update(self, **kwargs):
        self._data.update(kwargs)

    async def finish(self, values=None):
        val = await super().finish(values=values)
        txn = get_transaction(self.request)
        txn.add_after_commit_hook(self._delete_key)
        return val

    async def _delete_key(self):
        # and clear the cache key
        redis = await self.get_redis()
        key = self.get_key()
        await redis.delete(key)
