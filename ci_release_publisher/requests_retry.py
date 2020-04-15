# -*- coding: utf-8 -*-

from requests.adapters import HTTPAdapter
import requests

from . import config
from . import env

def requests_retry():
    session = requests.Session()
    retry = config.retries()

    debug = env.optional('CIRP_DEBUG')
    if debug == '1':
        retry.raise_on_status=False
        def add_response_to_exeption(session, fn_name):
            fn_old = getattr(session, fn_name)
            def fn_new(*args, **kwargs):
                try:
                    r = fn_old(*args, **kwargs)
                    r.raise_for_status()
                    return r
                except requests.exceptions.HTTPError as e:
                    raise type(e)('{}\n{}\n{}'.format(r.headers, r.text, str(e)))
        add_response_to_exeption(session, 'get')
        add_response_to_exeption(session, 'post')

    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    return session
