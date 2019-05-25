# -*- coding: utf-8 -*-

import pytest

from ci_release_publisher import config, temporary_store_release

tag_name_tests = [
    ('branch', '123456789', '987654321', ['{}-branch-123456789-987654321-{}', '{}{}-branch-123456789-987654321-{}']),
    ('-branch-_name-', '123456789', '987654321', ['{}--branch-_name--123456789-987654321-{}', '{}{}--branch-_name--123456789-987654321-{}']),
]

def test_tag_name():
    for branch, build_number, job_number, expected in tag_name_tests:
        expect = expected[0].format(config.tag_prefix, temporary_store_release._tag_suffix)
        assert temporary_store_release._tag_name(branch, build_number, job_number) == expect
        assert temporary_store_release._break_tag_name(expect)
        assert temporary_store_release._break_tag_name(expect)['branch'] == branch
        assert temporary_store_release._break_tag_name(expect)['build_number'] == build_number
        assert temporary_store_release._break_tag_name(expect)['job_number'] == job_number

def test_tag_name_tmp():
    for branch, build_number, job_number, expected in tag_name_tests:
        expect = expected[1].format(config.tag_prefix_tmp, config.tag_prefix, temporary_store_release._tag_suffix)
        assert temporary_store_release._tag_name_tmp(branch, build_number, job_number) == expect
        assert temporary_store_release._break_tag_name_tmp(expect)
        assert temporary_store_release._break_tag_name_tmp(expect)['branch'] == branch
        assert temporary_store_release._break_tag_name_tmp(expect)['build_number'] == build_number
        assert temporary_store_release._break_tag_name_tmp(expect)['job_number'] == job_number
