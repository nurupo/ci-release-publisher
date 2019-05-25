# -*- coding: utf-8 -*-

from urllib3.util.retry import Retry

from .__version__ import __title__, __version__

user_agent = '{} {}'.format(__title__, __version__)
tag_prefix = 'ci'
tag_prefix_tmp = '_'
timeout = 15

def retries():
    return Retry(total=7, backoff_factor=0.1, status_forcelist=[403, 500, 502, 503, 504], method_whitelist=list(Retry.DEFAULT_METHOD_WHITELIST)+['POST'])
