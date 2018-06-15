

import random
import gc
import time
import resource

from guillotina_rediscache.lru import LRU

on
_passes = 10000


def rbytes(size=1):
    return bytearray(random.getrandbits(8) for _ in range(int(size)))


def gen_data(serie):
    return [rbytes(k) for k in serie]


def action(passes, writ=0.5):
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

P4 = [K, K, K, M, 5*M, K/2, K/2, K/2, K, K, K, K, K, K/2, K/4, K/3, 2*M, K, K,
      K, K, K, K, K, K*5]


def get_memory():
    gc.collect()
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


if __name__ == "__main__":
    serie = create_serie(gen_data(P4), action(_passes))
    c = LRU(300*M)
    pase = 1
    while True:
        run_cache(c, serie)
        print(f'Pase: {pase} \t Memory: {get_memory()}/{c.get_memory()} // {c.get_stats()}')
        time.sleep(0.2)
        pase += 1