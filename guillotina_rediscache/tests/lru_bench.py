
import random
import pytest
import gc

from lru import LRU
from guillotina_rediscache.lru import LRU as LRUS
import resource

_passes = 10000


def rbytes(size=1):
    return bytearray(random.getrandbits(8) for _ in range(int(size)))


def gen_data(serie):
    return [rbytes(k) for k in serie]


def action(passes, writ=0.1):
    ACTION = []
    for k in range(passes):
        if random.random() > writ:
            ACTION.append("r")
        else:
            ACTION.append("w")
    return ACTION


def run_cache(cache, serie):
    for i in range(3):
        for step in serie:
            if step[0] == "w":
                if isinstance(cache, LRU):
                    cache[step[1]] = step[2]
                else:
                    cache.set(step[1], step[2], len(step[2]))
            else:
                cache.get(step[1], None)


def create_serie(items, actions, mkeys=3000, passes=10000):
    serie = []
    for k in range(passes):
        key = str(random.randrange(0, mkeys))
        if actions[k] == "w":
            serie.append(('w', key, random.choice(items)))
        else:
            serie.append(('r', key))
    return serie


K = 1024
M = K * 1024

P0 = [10*M]
P1 = [K, K, K, M, 5*M, K/2, K/2, K/2, K, K, K, K/2, K/2, K/2, K/2, K/2]
P2 = [K, K, K, K/2, K/2, K/2, K/2, K/2]
P3 = [5*M, 10*M, M, 2*M, 4*M, 3*M, 1*M, 7*M, 5*M]
P4 = [K, K, K, M, 5*M, K/2, K/2, K/2, K, K, K, K, K, K/2, K/4, K/3, 2*M, K, K,
      K, K, K, K, K, K*5]
P5 = [64]
P6 = [10*M, 64]


# serie = create_serie(gen_data(P4), action(_passes))
@pytest.fixture(scope="session", params=[P0, P1, P2, P3, P4, P5, P6])
def data(request):
    return create_serie(gen_data(request.param), action(_passes))


results = {}
base = dict(
    hits=0,
    misses=0,
    items=0,
    clean=0,
    fullclean=0,
    memory=0,
    size=0
)


def sessionfinish():
    print(f"\n\nCache Stats:\n=======\n{'Id'.ljust(40)}\tHits\tMisses\tMemory\tItems\tClean\tFC\tSize")
    print("----------")
    for key, val in results.items():
        id = key.split("::")[1]
        print(f"{id.ljust(40)}\t{val['hits']}\t{val['misses']}\t{val['memory']}"
              f"\t{val['items']}\t{val['clean']}\t{val['fullclean']}\t{val['size']}")


@pytest.fixture(scope="session")
def reporter(request):
    request.addfinalizer(sessionfinish)


@pytest.fixture(scope="function")
def collector(request, reporter):
    def data(stats):
        res = base.copy()
        res.update(stats)
        results[request.node._nodeid] = res
    yield data


def test_bench_with_lru(benchmark, data, collector):
    m = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    c2 = LRUS(300*M)
    benchmark.pedantic(run_cache, args=(c2, data),
                       iterations=1, rounds=100)
    assert c2.get_memory() <= (300*M)
    hits, misses, clean = c2.get_stats()
    collector(dict(
        hits=hits,
        misses=misses,
        clean=clean,
        items=len(c2.keys()),
        memory=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss-m
    ))


def test_bench_with_original(benchmark, data, collector):
    m = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    c1 = LRU(2000)
    benchmark.pedantic(run_cache, args=(c1, data),
                       iterations=1, rounds=100)
    hits, misses = c1.get_stats()
    items = len(c1.keys())
    del c1
    gc.collect()
    collector(dict(
        hits=hits,
        misses=misses,
        items=items,
        memory=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss-m
    ))
