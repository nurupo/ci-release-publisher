# -*- coding: utf-8 -*-

from requests.adapters import HTTPAdapter
import requests

from . import config

def requests_retry():
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=config.retries())
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
