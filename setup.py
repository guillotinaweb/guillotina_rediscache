# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup
from setuptools import Extension
from Cython.Build import cythonize


module1 = Extension('lrus', sources = ['guillotina_rediscache/lru.c'])
# module2 = cythonize("guillotina_rediscache/lrusize.pyx")
module2 = []

setup(
    name='guillotina_rediscache',
    version='1.3.5.dev0',
    description='guillotina cache implementation using '
                'redis + lru in-memory cache',
    long_description=(open('README.rst').read() + '\n' +
                      open('CHANGELOG.rst').read()),
    keywords=['asyncio', 'REST', 'guillotina', 'cache', 'redis'],
    author='Nathan Van Gheem',
    author_email='vangheem@gmail.com',
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    url='https://github.com/guillotinaweb/guillotina_rediscache',
    license='BSD',
    setup_requires=[
        'pytest-runner',
    ],
    zip_safe=True,
    include_package_data=True,
    ext_modules=[module1] + module2,
    packages=find_packages(),
    install_requires=[
        'guillotina>=2.3.10',
        'aioredis>=1.0.0',
        'lru-dict',
        'ujson'
    ],
    extras_require={
        'test': [
            'pytest',
            'docker',
            'backoff',
            'pytest-asyncio<=0.5.0',
            'pytest-aiohttp',
            'pytest-cov',
            'pytest-docker-fixtures>=1.1.0'
        ]
    }
)
