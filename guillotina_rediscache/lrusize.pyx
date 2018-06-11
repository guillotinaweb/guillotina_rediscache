# cython: language_level=3

from sys import getsizeof
from cpython cimport Py_DECREF, Py_INCREF

cdef _get_size(object obj, seen=None):
    """Recursively finds size of objects"""
    size = getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)
    if isinstance(obj, dict):
        size += sum([get_size(v, seen) for v in obj.values()])
        size += sum([get_size(k, seen) for k in obj.keys()])
    elif hasattr(obj, '__dict__'):
        size += get_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum([get_size(i, seen) for i in obj])
    return size


def get_size(obj, default=None):
    res = _get_size(obj)
    if res is 0:
        return default
    return res


cdef class Node:
    cdef:
        object value
        object key
        long size
        Node prev
        Node next


cdef class LRUS:
    cdef:
        dict data
        Node first
        Node last
        long size
        long hits
        long misses

    cdef public:
        long memory

    def __cinit__(self, long size):
        self.data = dict()
        self.first = self.last = None
        self.size = size
        self.memory = self.hits = self.misses = 0

    cdef remove_node(self, Node node):

        if self.first == node:
            self.first = node.next
        if self.last == node:
            self.last = node.prev
        if node.prev:
            node.prev.next = node.next
        if node.next:
            node.next.prev = node.prev
        node.next = node.prev = None

    cdef add_node_at_head(self, Node node):
        node.prev = None
        if not self.first:
            self.first = self.last = node
            node.next = None
        else:
            node.next = self.first
            if node.next:
                node.next.prev = node
            self.first = node

    cdef delete_last(self):
        cdef Node node
        if not self.last:
            return
        node = self.last
        self.remove_node(node)
        del self.data[node.key]


    def __contains__(self, key):
        return key in self.data

    def __getitem__(self, key):
        cdef Node node
        try:
            node = self.data[key]
        except KeyError:
            self.misses += 1
            return None
        if node != self.first:
            self.remove_node(node)
            self.add_node_at_head(node)
        self.hits += 1
        # Py_INCREF(node.value)
        # Py_DECREF(node)
        return node.value

    def __setitem__(self, key, value):
        self._set(key, value)

    cdef _set(self, key, value, long memory=0):
        cdef:
            Node node
        try:
            node = self.data[key]
        except KeyError:
            node = None

        if node:
            # Py_INCREF(value)
            # Py_DECREF(node.value)
            node.value = value
            if memory == 0:
                memory = get_size(value)
            self.memory = self.memory + memory - node.size
            node.size = memory
            self.remove_node(node)
            self.add_node_at_head(node)
        else:
            node = Node()
            node.key = key
            node.value = value
            node.next = node.prev = None
            if memory == 0:
                memory = get_size(value)
            node.size = memory
            self.memory += memory

            # Py_INCREF(key)
            # Py_INCREF(value)
            self.data[key] = node
            self.add_node_at_head(node)

        self.vacumm()


    def __delitem__(self, key):
        cdef:
            Node node
        try:
            node = self.data[key]
        except KeyError:
            node = None

        if node:
            self.memory -= node.size
            self.remove_node(node)
            del self.data[key]


    def get(self, key, default):
        val = self[key]
        if not val:
            return default
        return val

    def set(self, key, val, memory=0):
        self._set(key, val, memory)

    cdef vacumm(self):
        while self.memory > self.size:
            self.memory -= self.last.size
            self.delete_last()

    def get_stats(self):
        return self.hits, self.misses, len(self.data.keys())