# -*- coding: utf-8 -*-

from github import GithubObject
import logging
import re

from . import config
from . import enum
from . import env
from . import github
from . import travis

_tag_suffix = 'latest'

def _tag_name(travis_branch):
    return '{}-{}-{}'.format(config.tag_prefix, travis_branch, _tag_suffix)

def _break_tag_name(tag_name):
    if not tag_name.startswith(config.tag_prefix) or not tag_name.endswith(_tag_suffix):
        return None
    tag_name = tag_name[len(config.tag_prefix):-len(_tag_suffix)]
    m = re.match('^-(?P<branch>.*)-$', tag_name)
    if not m:
        return None
    return {'matched': True, 'branch': m.group('branch')}

def _tag_name_tmp(travis_branch):
    return '{}{}'.format(config.tag_prefix_tmp, _tag_name(travis_branch))

def _break_tag_name_tmp(tag_name):
    if not tag_name.startswith(config.tag_prefix_tmp):
        return None
    tag_name = tag_name[len(config.tag_prefix_tmp):]
    return _break_tag_name(tag_name)

def publish_args(parser):
    parser.add_argument('--latest-release', default=False, action='store_true',
                        help='Publish latest release. The same "{}-<branch>-{}" tag release will be re-used (re-created) by each build.'.format(config.tag_prefix, _tag_suffix))
    parser.add_argument('--latest-release-name', type=str, help='Release name text. If not specified a predefined text is used.')
    parser.add_argument('--latest-release-body', type=str, help='Release body text. If not specified a predefined text is used.')
    parser.add_argument('--latest-release-draft', default=False, action='store_true', help='Publish as a draft.')
    parser.add_argument('--latest-release-prerelease', default=False, action='store_true', help='Publish as a prerelease.')
    parser.add_argument('--latest-release-target-commitish', type=str,
                        help='Commit the release should point to. By default it\'s set to $TRAVIS_COMMIT when publishing to the same repo and not set when publishing to a different repo.')
    parser.add_argument('--latest-release-check-event-type', default=['any'], nargs='+', type=str, choices=enum.enum_to_arg_choices(travis.Travis.EventType),
                        help='Consider only builds of specific event types when checking if the current build is the latest. If not specified, "any" is used.')

def publish_validate_args(args):
    return args.latest_release

def publish_with_args(args, releases, artifact_dir, github_api_url, travis_api_url):
    if not args.latest_release:
        return
    publish(releases, artifact_dir, args.latest_release_name, args.latest_release_body, args.latest_release_draft, args.latest_release_prerelease, args.latest_release_target_commitish,
            enum.arg_choices_to_enum(travis.Travis.EventType, args.latest_release_check_event_type), github_api_url, travis_api_url)

def publish(releases, artifact_dir, latest_release_name, latest_release_body, latest_release_draft, latest_release_prerelease, latest_release_target_commitish, latest_release_check_event_type, github_api_url, travis_api_url):
    github_token         = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    github_repo_slug     = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')
    travis_repo_slug     = env.required('TRAVIS_REPO_SLUG')
    travis_branch        = env.required('TRAVIS_BRANCH')
    travis_commit        = env.required('TRAVIS_COMMIT')
    travis_build_number  = env.required('TRAVIS_BUILD_NUMBER')
    travis_build_id      = env.required('TRAVIS_BUILD_ID')
    travis_build_web_url = env.required('TRAVIS_BUILD_WEB_URL')
    travis_tag           = env.optional('TRAVIS_TAG')
    travis_token         = env.optional('CIRP_TRAVIS_ACCESS_TOKEN')

    if travis_tag:
        return
    tag_name = _tag_name(travis_branch)
    logging.info('* Creating a latest release with the tag name "{}".'.format(tag_name))

    def _is_latest_build_for_branch():
        if int(travis.Travis(travis_api_url, travis_token, github_token).branch_last_build_number(travis_repo_slug, travis_branch, latest_release_check_event_type)) == int(travis_build_number):
            return True
        logging.info('Not creating the "{}" release because this is not the latest build for "{}" branch with event type(s): {}.'.format(tag_name, travis_branch, ','.join([e.name.lower() for e in latest_release_check_event_type])))
        return False

    if not _is_latest_build_for_branch():
        return
    tag_name_tmp = _tag_name_tmp(travis_branch)
    logging.info('Creating a draft release with the tag name "{}".'.format(tag_name_tmp))
    release = github.github(github_token, github_api_url).get_repo(github_repo_slug).create_git_release(
        tag=tag_name_tmp,
        name=latest_release_name if latest_release_name else
             'Latest CI build of {} branch'.format(travis_branch),
        message=latest_release_body if latest_release_body else
                'This is an auto-generated release based on [Travis-CI build #{}]({})'
                .format(travis_build_id, travis_build_web_url),
        draft=True,
        prerelease=latest_release_prerelease,
        target_commitish=latest_release_target_commitish if latest_release_target_commitish else travis_commit if not env.optional('CIRP_GITHUB_REPO_SLUG') else GithubObject.NotSet)
    github.upload_artifacts(artifact_dir, release)
    if not _is_latest_build_for_branch():
        github.delete_release_with_tag(release, github_token, github_api_url, github_repo_slug)
        return
    previous_release = [r for r in releases if r.tag_name == tag_name]
    if previous_release:
        github.delete_release_with_tag(previous_release[0], github_token, github_api_url, github_repo_slug)
    logging.info('Changing the tag name from "{}" to "{}"{}.'.format(tag_name_tmp, tag_name, '' if latest_release_draft else ' and removing the draft flag'))
    release.update_release(name=release.title, message=release.body, prerelease=release.prerelease, target_commitish=release.target_commitish, draft=latest_release_draft, tag_name=tag_name)

def cleanup(releases, branch_unfinished_build_numbers, github_api_url):
    github_token        = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    github_repo_slug    = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')
    travis_branch       = env.required('TRAVIS_BRANCH')
    travis_build_number = env.required('TRAVIS_BUILD_NUMBER')
    travis_tag          = env.optional('TRAVIS_TAG')

    if travis_tag:
        return
    logging.info('* Deleting incomplete latest releases left over due to jobs failing or being cancelled.')
    # FIXME(nurupo): once Python 3.8 is out, use Assignemnt Expression to prevent expensive _break_tag_name() calls https://www.python.org/dev/peps/pep-0572/
    latest_releases_incomplete = [r for r in releases if r.draft and
                                  _break_tag_name_tmp(r.tag_name) and
                                  _break_tag_name_tmp(r.tag_name)['branch'] == travis_branch]
    if not latest_releases_incomplete or any(n != travis_build_number for n in branch_unfinished_build_numbers):
        return
    for r in latest_releases_incomplete:
        try:
            github.delete_release_with_tag(r, github_token, github_api_url, github_repo_slug)
        except Exception as e:
            logging.warning('{}: {}'.format(type(e).__name__, e))
