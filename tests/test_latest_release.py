# -*- coding: utf-8 -*-

import pytest

from ci_release_publisher import config, latest_release

tag_name_tests = [
    ('branch', ['{}-branch-{}', '{}{}-branch-{}']),
    ('-branch-_name-', ['{}--branch-_name--{}', '{}{}--branch-_name--{}']),
]

def test_tag_name():
    for branch, expected in tag_name_tests:
        expect = expected[0].format(config.tag_prefix, latest_release._tag_suffix)
        assert latest_release._tag_name(branch) == expect
        assert latest_release._break_tag_name(expect)
        assert latest_release._break_tag_name(expect)['branch'] == branch

def test_tag_name_tmp():
    for branch, expected in tag_name_tests:
        expect = expected[1].format(config.tag_prefix_tmp, config.tag_prefix, latest_release._tag_suffix)
        assert latest_release._tag_name_tmp(branch) == expect
        assert latest_release._break_tag_name_tmp(expect)
        assert latest_release._break_tag_name_tmp(expect)['branch'] == branch
