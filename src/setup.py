#!/usr/bin/env python
# encoding: utf-8

from distutils.core import setup
from pvaurora import __version__
setup(name='pvaurora',
      version=__version__,
      description='Aurora power inverter uploader to pvoutput.org',
      url='https://github.com/yuroller/pvaurora',
      author='Yuri Valentini',
      author_email='yv@opycom.it',
      py_modules=['pvaurora', 'timezone', 'sun', 'config'])