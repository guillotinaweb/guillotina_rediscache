

import random

from guillotina_rediscache.lru import LRU


_bytes = b'x' * 3


def test_lrusized_acts_like_a_dict():
    m = LRU(1024)
    m.set('a', _bytes, 3)
    assert m['a'] == _bytes
    assert 'a' in m.keys()
    assert m.get_memory() == 3
    del m['a']
    assert len(m.keys()) == 0
    assert m.get_memory() == 0


def test_clean_till_it_has_enought_space():
    m = LRU(100)
    for k in range(100):
        m.set(k, k, 1)
    





