#!/usr/bin/env python3

from setuptools import setup, find_packages
from os import path
from io import open

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='python-make-jobserver',
    version='0.0.1',

    description="Python library for working for make's jobserver system",
    long_description=long_description,
    long_description_content_type='text/markdown',

    url='https://github.com/mithro/python-make-jobserver',

    author="Tim 'mithro' Ansell",
    author_email='me@mith.ro',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: Apache 2.0',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],

    keywords='make gnumake jobserver development',

    packages=find_packages(exclude=['docs', 'tests']),

    # Python ==2.7 or Python =>3.5
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, <4',

    install_requires=[],
    extras_require={
        'dev': ['check-manifest'],
        'test': ['coverage'],
    },

    #entry_points={
    #    'console_scripts': [
    #        'sample=sample:main',
    #    ],
    #},

    project_urls={  # Optional
        'Bug Reports': 'https://github.com/mithro/python-make-jobserver/issues',
        'Source': 'https://github.com/mithro/python-make-jobserver/',
    },
)
