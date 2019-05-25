# -*- coding: utf-8 -*-

import os

from . import exception

def required(name):
    if name not in os.environ:
        raise exception.CIReleasePublisherError('Required environment variable "{}" is not set.'.format(name))
    return os.environ[name]

def optional(name):
    if name not in os.environ:
        return None
    return os.environ[name]
