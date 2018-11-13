from guillotina import testing

import pytest


def settings_configurator(settings):
    if 'applications' in settings:
        settings['applications'].append('guillotina_rediscache')
    else:
        settings['applications'] = ['guillotina_rediscache']
    del settings['static']
    del settings['jsapps']
    settings["redis"] = {
        'host': getattr(redis_container, 'host', 'localhost'),
        'port': getattr(redis_container, 'port', 6379),
        'ttl': 3600,
        'memory_cache_size': 200 * 1024 * 1024,
        'updates_channel': 'guillotina',
        'pool': {
            'minsize': 5,
            'maxsize': 100
        }
    }
    settings["load_utilities"]["guillotina_rediscache.cache"] = {
        "provides": "guillotina_rediscache.interfaces.IRedisChannelUtility",  # noqa
        "factory": "guillotina_rediscache.utility.RedisChannelUtility",
        "settings": {}
    }


testing.configure_with(settings_configurator)


@pytest.fixture(scope='session')
def redis_container(redis):
    setattr(redis_container, 'host', redis[0])
    setattr(redis_container, 'port', redis[1])

    yield redis
