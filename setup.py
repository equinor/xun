#!/usr/bin/env python3

import setuptools


if __name__ == '__main__':
    #
    # This check is needed to allow multiprocessing tests to run
    #
    setuptools.setup(
        name = 'xun',
        version='1.0.0',
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
            'xun.functions',
            'xun.functions.compatibility',
            'xun.functions.driver',
            'xun.functions.store',
            'xun.init',
        ],
        platforms = 'any',
        include_package_data=True,

        install_requires = [
            'astor',
            'cookiecutter',
            'cryptography',
            'dask[distributed]',
            'immutables',
            'matplotlib',
            'nbformat',
            'networkx',
            'numpy',
            'pandas',
            'paramiko',
            'redis',
            'yapf',
        ],

        setup_requires = [
            'setuptools >=28',
            'setuptools_scm',
            'pytest-runner',
        ],

        python_requires='>=3',

        tests_require = [
            'fakeredis',
            'mock-ssh-server',
            'pyshd',
            'pytest',
            'pyshd',
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
