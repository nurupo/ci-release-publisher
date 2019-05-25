# -*- coding: utf-8 -*-

import requests

from . import config
from .requests_retry import requests_retry

# Apparently there is no Traivis API python library that supports the latest API version (v3).
# There is travispy, it supports v2 (v2 is being phased out this (2018) year) and it doesn't
# allow to get the info we need, so we roll out our own awfully specific Travis API class.
class Travis:
    _headers = {
        'Travis-API-Version': '3',
        'User-Agent': config.user_agent,
    }

    def __init__(self, travis_token, travis_api_url):
        self._api_url = travis_api_url
        self._headers['Authorization'] = 'token {}'.format(travis_token)

    @classmethod
    def github_auth(cls, github_token, travis_api_url):
        # We have to use API 2.1 to get Travis-CI token based on GitHub token.
        # See https://github.com/travis-ci/travis-ci/issues/9273.
        # API 2.1 is supposedly getting deprecated sometime in 2018, so hopefully a similar endpoint
        # will be added to the version 3 of the API. If not, we can start requiring the user to
        # provide their Travis API token in the future.
        headers = {
            'Accept': 'application/vnd.travis-ci.2.1+json',
            'User-Agent': cls._headers['User-Agent'],
        }
        # API doc: https://docs.travis-ci.com/api/?http#with-a-github-token
        response = requests_retry().post('{}/auth/github'.format(travis_api_url), headers=headers, params={'github_token': github_token}, timeout=config.timeout)
        return Travis(response.json()['access_token'], travis_api_url)

    # Returns last build number for a branch
    def branch_last_build_number(self, repo_slug, branch_name):
        _repo_slug = requests.utils.quote(repo_slug, safe='')
        _branch_name = requests.utils.quote(branch_name, safe='')
        # API doc: https://developer.travis-ci.com/resource/branch
        response = requests_retry().get('{}/repo/{}/branch/{}'.format(self._api_url, _repo_slug, _branch_name), headers=self._headers, timeout=config.timeout)
        return response.json()['last_build']['number']

    # Returns a list of build numbers of all builds that have not finished for a branch.
    # "not finished" basically means that a build is active (queued/running). it could be a restarted build too.
    # Note that the returned build numbers are str, not int.
    def branch_unfinished_build_numbers(self, repo_slug, branch_name):
        _repo_slug = requests.utils.quote(repo_slug, safe='')
        _branch_name = requests.utils.quote(branch_name, safe='')
        # There is no good way to request all builds for a branch, you can request only last 10 with
        # https://developer.travis-ci.com/resource/branch end point, which is not good enough, so we
        # just request all builds in general, sort them by unfinished first and filter by branch ourselves.
        build_numbers = []
        limit = 100 # Doesn't seem like the API allows to set this any higher, it caps at 100
        offset = 0
        count = offset + 1 # Just something to make the while condition true for the first run, it gets overwritten in the loop
        # `count` is how many there are builds in total and `offset` is how far are we in.
        while offset < count:
            params = {
                # This will put all builds that have not finished yet first as their 'finished_at' is null
                'sort_by': 'finished_at:desc',
                'offset': offset,
                'limit': limit,
            }
            # API doc: https://developer.travis-ci.com/resource/builds
            response = requests_retry().get('{}/repo/{}/builds'.format(self._api_url, _repo_slug, _branch_name), headers=self._headers, params=params, timeout=config.timeout)
            json = response.json()
            offset += json['@pagination']['limit']
            count = json['@pagination']['count']
            # We filter by repository slug too because there might be builds of PRs from forks with the same branch name as ours, we don't want to include those
            branch_builds = [build for build in json['builds'] if build['branch']['name'] == branch_name and build['repository']['slug'] == repo_slug]
            build_numbers.extend([build['number'] for build in branch_builds if build['finished_at'] == None])
            # If we find a finished build, then there is no point in looking any further as we sort
            # them by `finished_at` field -- there would be no unfinished builds any further.
            if any(build['finished_at'] != None for build in branch_builds):
                break
        return build_numbers

    # Returns True if the build has a job that both has failed and doesn't have allow_failure set on it.
    def build_has_failed_nonallowfailure_job(self, build_id):
        # API doc: https://developer.travis-ci.com/resource/build
        # API doc: https://developer.travis-ci.com/resource/jobs
        params = {
            'include': 'job.allow_failure,job.state',
        }
        response = requests_retry().get('{}/build/{}'.format(self._api_url, build_id), headers=self._headers, params=params, timeout=config.timeout)
        return any([j for j in response.json()['jobs'] if j['state'] == 'failed' and not j['allow_failure']])
