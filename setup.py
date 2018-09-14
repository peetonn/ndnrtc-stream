"""Packaging settings."""


from codecs import open
from os.path import abspath, dirname, join
from subprocess import call

from setuptools import Command, find_packages, setup

from ndnrtc_stream import __version__


this_dir = abspath(dirname(__file__))
with open(join(this_dir, 'README.md'), encoding='utf-8') as file:
    try:
        import pypandoc
        long_description = pypandoc.convert_text(file.read(), 'rst', format='md')
    except (IOError, ImportError):
        long_description = ''

class RunTests(Command):
    """Run all tests."""
    description = 'run tests'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        """Run all tests!"""
        errno = call(['py.test', '--cov=ndnrtc-stream', '--cov-report=term-missing'])
        raise SystemExit(errno)


setup(
    name = 'ndnrtc-stream',
    version = __version__,
    description = 'A Python wrapper for ndnrtc-client for quick&easy stream publishing and fetching over NDN.',
    long_description = long_description,
    url = 'https://github.com/remap/ndnrtc-stream',
    author = 'Peter Gusev',
    author_email = 'peter@remap.ucla.edu',
    license = 'UNLICENSED',
    classifiers = [
        'Intended Audience :: Developers',
        'Topic :: Utilities',
        'License :: Public Domain',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    keywords = 'NDN ndnrtc ndnrtc-client',
    packages = find_packages(exclude=['docs', 'tests*']),
    install_requires = ['docopt', 'docopt', 'libconf'],
    extras_require = {
        'test': ['coverage', 'pytest', 'pytest-cov'],
    },
    entry_points = {
        'console_scripts': [
            'ndnrtc-stream=ndnrtc_stream.cli:main',
        ],
    },
    cmdclass = {'test': RunTests},
)
