#!/usr/bin/python

from distutils.core import setup

setup(name="pyserf",
      version="1.0",
      scripts = ['pyserf.py'],
      data_files = [('/usr/local/include', ['pyserf_helpers.c'])],      
     )


