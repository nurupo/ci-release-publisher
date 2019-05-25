# -*- coding: utf-8 -*-

from enum import Enum, auto, unique
from github import GithubObject
import logging
import re

from . import config
from . import env
from . import github
from . import travis

_tag_suffix = 'tmp'

def _tag_name(travis_branch, travis_build_number, travis_job_number):
    return '{}-{}-{}-{}-{}'.format(config.tag_prefix, travis_branch, travis_build_number, travis_job_number, _tag_suffix)

def _break_tag_name(tag_name):
    if not tag_name.startswith(config.tag_prefix) or not tag_name.endswith(_tag_suffix):
        return None
    tag_name = tag_name[len(config.tag_prefix):-len(_tag_suffix)]
    m = re.match('^-(?P<branch>.*)-(?P<build_number>\d+)-(?P<job_number>\d+)-$', tag_name)
    if not m:
        return None
    return {'branch': m.group('branch'), 'build_number': m.group('build_number'), 'job_number': m.group('job_number')}

def _tag_name_tmp(travis_branch, travis_build_number, travis_job_number):
    return '{}{}'.format(config.tag_prefix_tmp, _tag_name(travis_branch, travis_build_number, travis_job_number))

def _break_tag_name_tmp(tag_name):
    if not tag_name.startswith(config.tag_prefix_tmp):
        return None
    tag_name = tag_name[len(config.tag_prefix_tmp):]
    return _break_tag_name(tag_name)

def publish_args(parser):
    parser.add_argument('--release-name', type=str, help='Release name text. If not specified a predefined text is used.')
    parser.add_argument('--release-body', type=str, help='Release body text. If not specified a predefined text is used.')

def publish_with_args(args, releases, artifact_dir, github_api_url, travis_api_url, travis_url):
    publish(releases, artifact_dir, args.release_name, args.release_body, github_api_url, travis_url)

def publish(releases, artifact_dir, release_name, release_body, github_api_url, travis_url):
    github_token        = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    github_repo_slug    = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')
    travis_repo_slug    = env.required('TRAVIS_REPO_SLUG')
    travis_branch       = env.required('TRAVIS_BRANCH')
    travis_commit       = env.required('TRAVIS_COMMIT')
    travis_build_number = env.required('TRAVIS_BUILD_NUMBER')
    travis_job_number   = env.required('TRAVIS_JOB_NUMBER').split('.')[1]
    travis_job_id       = env.required('TRAVIS_JOB_ID')

    tag_name = _tag_name(travis_branch, travis_build_number, travis_job_number)
    logging.info('* Creating a temporary store release with the tag name "{}".'.format(tag_name))
    tag_name_tmp = _tag_name_tmp(travis_branch, travis_build_number, travis_job_number)
    logging.info('Creating a release with the tag name "{}".'.format(tag_name_tmp))
    release = github.github(github_token, github_api_url).get_repo(github_repo_slug).create_git_release(
        tag=tag_name_tmp,
        name=release_name if release_name else
             'Temporary store release {}'
             .format(tag_name),
        message=release_body if release_body else
                ('Auto-generated temporary release containing build artifacts of [Travis-CI job #{}]({}/{}/jobs/{}).\n\n'
                'This release was created by the CI Release Publisher script, which will automatically delete it in the current or following builds.\n\n'
                'You should not manually delete this release, unless you don\'t use the CI Release Publisher script anymore.')
                .format(travis_job_id, travis_url, travis_repo_slug, travis_job_id),
        draft=True,
        prerelease=True,
        target_commitish=travis_commit if not env.optional('CIRP_GITHUB_REPO_SLUG') else GithubObject.NotSet)
    github.upload_artifacts(artifact_dir, release)
    logging.info('Changing the tag name from "{}" to "{}".'.format(tag_name_tmp, tag_name))
    release.update_release(name=release.title, message=release.body, prerelease=release.prerelease, target_commitish=release.target_commitish, draft=release.draft, tag_name=tag_name)

@unique
class CleanupScope(Enum):
    CURRENT_JOB = auto()
    CURRENT_BUILD = auto()
    PREVIOUS_FINISHED_BUILDS = auto()

@unique
class CleanupRelease(Enum):
    COMPLETE = auto()
    INCOMPLETE = auto()

def _enum_to_choices(enum_calss):
    return [e.name.lower().replace('_', '-') for e in enum_calss]

def _choices_to_enum(enum_calss, choices):
    return [enum_calss[s.upper().replace('-', '_')] for s in choices]

def cleanup_args(parser):
    parser.add_argument('--scope', nargs='+', type=str, choices=_enum_to_choices(CleanupScope), required=True, help="Scope to cleanup.")
    parser.add_argument('--release', nargs='+', type=str, choices=_enum_to_choices(CleanupRelease), required=True, help="Release to cleanup.")
    parser.add_argument('--on-nonallowed-failure', default=False, action='store_true',
                        help='Cleanup only if the current build has a job that both has failed and doesn\'t have allow_failure set on it, '
                             'i.e. the current build is going to fail once the current stage finishes running.')

def cleanup_with_args(args, releases, github_api_url, travis_api_url):
    cleanup(releases, _choices_to_enum(CleanupScope, args.scope), _choices_to_enum(CleanupRelease, args.release),
            args.on_nonallowed_failure, args.github_api_url, travis_api_url)

def cleanup(releases, scopes, release_completenesses, on_nonallowed_failure, github_api_url, travis_api_url):
    github_token         = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    github_repo_slug     = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')
    travis_repo_slug     = env.required('TRAVIS_REPO_SLUG')
    travis_branch        = env.required('TRAVIS_BRANCH')
    travis_build_number  = env.required('TRAVIS_BUILD_NUMBER')
    travis_build_id      = env.required('TRAVIS_BUILD_ID')
    travis_job_number    = env.required('TRAVIS_JOB_NUMBER').split('.')[1]
    travis_test_result   = env.optional('TRAVIS_TEST_RESULT')
    travis_allow_failure = env.optional('TRAVIS_ALLOW_FAILURE')

    logging.info('* Deleting temporary store releases.')

    if on_nonallowed_failure:
        # Jobs are marked as failed in the API only once they complete, so if we want to check if the current job has failed,
        # which has obviously hasn't completed yet since we are running, we have to check the env variables instead of
        # Travis-CI API, the API won't tell us this.
        has_nonallowed_failure = travis_test_result == '1' and travis_allow_failure == 'false'
        if not has_nonallowed_failure:
            # Alright, now check the API for other complete jobs
            has_nonallowed_failure = travis.Travis.github_auth(github_token, travis_api_url).build_has_failed_nonallowfailure_job(travis_build_id)
        if not has_nonallowed_failure:
            return

    branch_unfinished_build_numbers = []
    if CleanupScope.PREVIOUS_FINISHED_BUILDS in scopes:
        branch_unfinished_build_numbers = travis.Travis.github_auth(github_token, travis_api_url).branch_unfinished_build_numbers(travis_repo_slug, travis_branch)

    def should_delete(r):
        if not r.draft:
            return False

        info = None
        if not info and CleanupRelease.COMPLETE in release_completenesses:
            info = _break_tag_name(r.tag_name)
        if not info and CleanupRelease.INCOMPLETE in release_completenesses:
            info = _break_tag_name_tmp(r.tag_name)

        if not info:
            return False

        if info['branch'] != travis_branch:
            return False

        result = False
        if not result and CleanupScope.CURRENT_JOB in scopes:
            result = int(info['build_number']) == int(travis_build_number) and int(info['job_number']) == int(travis_job_number)
        if not result and CleanupScope.CURRENT_BUILD in scopes:
            result = int(info['build_number']) == int(travis_build_number)
        if not result and CleanupScope.PREVIOUS_FINISHED_BUILDS in scopes:
            result = int(info['build_number']) < int(travis_build_number) and info['build_number'] not in branch_unfinished_build_numbers
        return result

    releases_to_delete = [r for r in releases if should_delete(r)]

    # Sort for a better presentation when printing
    releases_to_delete = sorted(releases_to_delete, key=lambda r: not not _break_tag_name(r.tag_name))
    releases_to_delete = sorted(releases_to_delete, key=lambda r: int(_break_tag_name(r.tag_name)['job_number'] if _break_tag_name(r.tag_name)
                                                                      else _break_tag_name_tmp(r.tag_name)['job_number']))
    releases_to_delete = sorted(releases_to_delete, key=lambda r: int(_break_tag_name(r.tag_name)['build_number'] if _break_tag_name(r.tag_name)
                                                                      else _break_tag_name_tmp(r.tag_name)['build_number']))

    for release in releases_to_delete:
        try:
            github.delete_release_with_tag(release, github_token, github_api_url, github_repo_slug)
        except Exception as e:
            logging.warning('{}: {}'.format(type(e).__name__, e))

def download(releases, artifact_dir):
    github_token        = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    travis_branch       = env.required('TRAVIS_BRANCH')
    travis_build_number = env.required('TRAVIS_BUILD_NUMBER')

    logging.info('* Downloading temporary store releases created during this build.')

    # FIXME(nurupo): once Python 3.8 is out, use Assignemnt Expression to prevent expensive _break_tag_name() calls https://www.python.org/dev/peps/pep-0572/
    releases_stored = [r for r in releases if r.draft and
                       _break_tag_name(r.tag_name) and
                       _break_tag_name(r.tag_name)['branch'] == travis_branch and
                       int(_break_tag_name(r.tag_name)['build_number']) == int(travis_build_number)]
    # Sort for a better presentation when printing
    releases_stored = sorted(releases_stored, key=lambda r: int(_break_tag_name(r.tag_name)['job_number']))
    if not releases_stored:
        logging.info('Couldn\'t find any temporary store releases for this build.')
        return
    for release in releases_stored:
        github.download_artifcats(github_token, release, artifact_dir)
