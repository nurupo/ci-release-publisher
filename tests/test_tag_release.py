# -*- coding: utf-8 -*-

import pytest

from ci_release_publisher import config, tag_release

tag_name_tests = [
    ('tag', ['tag', '{}{}-tag-{}']),
    ('v123.1-tag-_name-', ['v123.1-tag-_name-', '{}{}-v123.1-tag-_name--{}']),
]

def test_tag_name():
    for tag, expected in tag_name_tests:
        expect = expected[0]
        assert tag_release._tag_name(tag) == expect
        assert tag_release._break_tag_name(expect)
        assert tag_release._break_tag_name(expect)['tag'] == tag

def test_tag_name_tmp():
    for tag, expected in tag_name_tests:
        expect = expected[1].format(config.tag_prefix_tmp, config.tag_prefix, tag_release._tmp_tag_suffix)
        assert tag_release._tag_name_tmp(tag) == expect
        assert tag_release._break_tag_name_tmp(expect)
        assert tag_release._break_tag_name_tmp(expect)['tag'] == tag
