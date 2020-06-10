#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name = 'xun',
    description = 'xun: package generated with cookiecutter-equinor',

    author = 'Equinor',
    author_email = 'jegm@equinor.com',
    url = 'https://github.com/equinor/xun',

    project_urls = {
        'Documentation': 'https://xun.readthedocs.io/',
        'Issue Tracker': 'https://github.com/equinor/xun/issues',
    },
    keywords = [
    ],

    license = 'GNU General Public License v3',

    packages = [
        'xun',
    ],
    platforms = 'any',

    install_requires = [
    ],

    setup_requires = [
        'setuptools >=28',
        'setuptools_scm',
        'pytest-runner'
    ],

    tests_require = [
        'pytest',
    ],

entry_points = {
        'console_scripts': [
            'xun = xun.cli:main',
        ],
    },

    use_scm_version = {
        'write_to': 'xun/version.py',
    },
)
