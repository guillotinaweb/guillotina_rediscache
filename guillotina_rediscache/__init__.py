from guillotina import configure


app_settings = {
    "redis": {
        'host': 'localhost',
        'port': 6379,
        'ttl': 3600,
        'memory_cache_size': 209715200,
        'updates_channel': 'guillotina',
        'pool': {
            'minsize': 5,
            'maxsize': 100
        },
        'cluster_mode': False
    },
    "load_utilities": {
        "guillotina_rediscache.cache": {
            'provides': 'guillotina_rediscache.interfaces.IRedisChannelUtility',  # noqa
            'factory': 'guillotina_rediscache.utility.RedisChannelUtility',
            'settings': {}
        }
    }
}


configure.permission('guillotina_rediscache.Manage', 'Manage redis cache')
configure.grant(
    permission="guillotina_rediscache.Manage",
    role="guillotina.Manager")


def includeme(root, settings):
    configure.scan('guillotina_rediscache.cache_strategy')
    configure.scan('guillotina_rediscache.utility')
    configure.scan('guillotina_rediscache.api')
    configure.scan('guillotina_rediscache.serialize')
