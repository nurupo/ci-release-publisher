# -*- coding: utf-8 -*-

import pytest

from ci_release_publisher import config, numbered_release

tag_name_tests = [
    ('branch', '123456789', ['{}-branch-123456789', '{}{}-branch-123456789']),
    ('-branch-_name-', '123456789', ['{}--branch-_name--123456789', '{}{}--branch-_name--123456789']),
]

def test_tag_name():
    for branch, build_number, expected in tag_name_tests:
        expect = expected[0].format(config.tag_prefix)
        assert numbered_release._tag_name(branch, build_number) == expect
        assert numbered_release._break_tag_name(expect)
        assert numbered_release._break_tag_name(expect)['branch'] == branch
        assert numbered_release._break_tag_name(expect)['build_number'] == build_number

def test_tag_name_tmp():
    for branch, build_number, expected in tag_name_tests:
        expect = expected[1].format(config.tag_prefix_tmp, config.tag_prefix)
        assert numbered_release._tag_name_tmp(branch, build_number) == expect
        assert numbered_release._break_tag_name_tmp(expect)
        assert numbered_release._break_tag_name_tmp(expect)['branch'] == branch
