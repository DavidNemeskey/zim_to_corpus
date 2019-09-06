#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

# I used the following resources to compile the packaging boilerplate:
# https://python-packaging.readthedocs.io/en/latest/
# https://packaging.python.org/distributing/#requirements-for-packaging-and-distributing

from setuptools import find_packages, setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(name='zim_to_corpus',
      version='0.1.0',
      description='Python package and scripts for reading and converting '
                  'the output of zim_to_dir (i.e. a corpus of Wikipedia '
                  'pages extracted from a .zim file) to various formats, '
                  'such as WP2 or BERT input.',
      long_description=readme(),
      url='https://github.com/DavidNemeskey/zim_to_corpus',
      author='Dávid Márk Nemeskey',
      license='LGPL',
      classifiers=[
          # How mature is this project? Common values are
          #   3 - Alpha
          #   4 - Beta
          #   5 - Production/Stable
          'Development Status :: 3 - Alpha',

          # Indicate who your project is intended for
          'Intended Audience :: Science/Research',
          'Topic :: Scientific/Engineering :: Information Analysis',
          # This one is not in the list...
          'Topic :: Scientific/Engineering :: Natural Language Processing',

          # Environment
          'Operating System :: POSIX :: Linux',
          'Environment :: Console',
          'Natural Language :: English',
          'Natural Language :: Hungarian',

          # Pick your license as you wish (should match "license" above)
          'License :: OSI Approved :: MIT License',

          # Specify the Python versions you support here. In particular, ensure
          # that you indicate whether you support Python 2, Python 3 or both.
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7'
      ],
      keywords='zim wikipedia wiki wp2 bert',
      packages=find_packages(exclude=['scripts', 'src']),
      # Install the scripts
      scripts=[
          'scripts/extract_zim_htmls.py',
      ],
      install_requires=[
          'beautifulsoup4',
          'lxml',
          'multiprocessing-logging',
      ],
      # zip_safe=False,
      use_2to3=False)

