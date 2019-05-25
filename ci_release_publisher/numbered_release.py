# -*- coding: utf-8 -*-

from github import GithubObject
import datetime
import logging
import re

from . import config
from . import env
from . import exception
from . import github
from . import travis

def _tag_name(travis_branch, travis_build_number):
    return '{}-{}-{}'.format(config.tag_prefix, travis_branch, travis_build_number)

def _break_tag_name(tag_name):
    if not tag_name.startswith(config.tag_prefix):
        return None
    tag_name = tag_name[len(config.tag_prefix):]
    m = re.match('^-(?P<branch>.*)-(?P<build_number>\d+)$', tag_name)
    if not m:
        return None
    return {'branch': m.group('branch'), 'build_number': m.group('build_number')}

def _tag_name_tmp(travis_branch, travis_build_number):
    return '{}{}'.format(config.tag_prefix_tmp, _tag_name(travis_branch, travis_build_number))

def _break_tag_name_tmp(tag_name):
    if not tag_name.startswith(config.tag_prefix_tmp):
        return None
    tag_name = tag_name[len(config.tag_prefix_tmp):]
    return _break_tag_name(tag_name)

def _retention_policy(releases, numbered_release_keep_count, numbered_release_keep_time, github_token, github_api_url, github_repo_slug, travis_branch, travis_build_number):
    logging.info('Executing retention policy rules.')
    # We want to enforce the retention policy only on the build numbers lower than ours. As to why,
    # imagine the case where build #10 for branch 'foo' has a rule to keep only last 3 numbered
    # builds. However, 'foo' is already at build #1000 and it has changed its retention policy
    # greatly since the 10th build, it now retains 50 last numbered releases. If someone were to
    # restart build #10 on Travis-CI, either by an accident or not, it would be disasterous if it
    # deleted the 50 numbered releases and kept just 3. That's why.
    # (To clarify a possible confusion, if you restart build #10 it remains being build #10, it
    # doesn't change its build number to, say, #1001.)
    # FIXME(nurupo): once Python 3.8 is out, use Assignemnt Expression to prevent expensive _break_tag_name() calls https://www.python.org/dev/peps/pep-0572/
    previous_numbered_releases = [r for r in releases if _break_tag_name(r.tag_name) and
                                                         _break_tag_name(r.tag_name)['branch'] == travis_branch and
                                                         int(_break_tag_name(r.tag_name)['build_number']) < int(travis_build_number)]
    # Sort for a better presentation when printing
    # Also, _retention_policy_by_count() relies on them being sorted in this exact order
    previous_numbered_releases = sorted(previous_numbered_releases, key=lambda r: int(_break_tag_name(r.tag_name)['build_number']))
    _retention_policy_by_count(previous_numbered_releases, numbered_release_keep_count, github_token, github_api_url, github_repo_slug, travis_branch)
    _retention_policy_by_time(previous_numbered_releases, numbered_release_keep_time, github_token, github_api_url, github_repo_slug, travis_branch)

def _retention_policy_by_count(previous_numbered_releases, numbered_release_keep_count, github_token, github_api_url, github_repo_slug, travis_branch):
    if numbered_release_keep_count <= 0:
        return
    logging.info('Keeping only {} numbered releases for "{}" branch.'.format(numbered_release_keep_count, travis_branch))
    extra_numbered_releases_to_remove = (len(previous_numbered_releases) + 1) - numbered_release_keep_count
    if extra_numbered_releases_to_remove < 0:
        extra_numbered_releases_to_remove = 0
    logging.info('Found {} previous numbered release(s) for "{}" branch. Accounting for the one we are about to create, {} of existing numbered releases must be deleted.'
                 .format(len(previous_numbered_releases), travis_branch, extra_numbered_releases_to_remove))
    for release in previous_numbered_releases[:extra_numbered_releases_to_remove]:
        try:
            github.delete_release_with_tag(release, github_token, github_api_url, github_repo_slug)
        except Exception as e:
            logging.warning('{}: {}'.format(type(e).__name__, e))
    previous_numbered_releases = previous_numbered_releases[extra_numbered_releases_to_remove:]

def _retention_policy_by_time(previous_numbered_releases, numbered_release_keep_time, github_token, github_api_url, github_repo_slug, travis_branch):
    if numbered_release_keep_time <= 0:
        return
    expired_previous_numbered_releases = [r for r in previous_numbered_releases if (datetime.datetime.now() - r.created_at).total_seconds() > numbered_release_keep_time]
    logging.info('Keeping numbered releases that are not older than {} seconds for "{}" branch.'.format(numbered_release_keep_time, travis_branch))
    logging.info('Found {} numbered release(s) for "{}" branch. {} of them will be deleted due to being too old.'
                 .format(len(previous_numbered_releases), travis_branch, len(expired_previous_numbered_releases)))
    for release in expired_previous_numbered_releases:
        try:
            github.delete_release_with_tag(release, github_token, github_api_url, github_repo_slug)
        except Exception as e:
            logging.warning('{}: {}'.format(type(e).__name__, e))
    previous_numbered_releases = [r for r in previous_numbered_releases if r not in expired_previous_numbered_releases]

def publish_args(parser):
    parser.add_argument('--numbered-release', default=False, action='store_true',
                        help='Publish a numbered release. A separate "{}-<branch>-<build_number>" release will be made for each build. '
                             'You must specify at least one of --numbered-release-keep-* arguments specifying the strategy for keeping numbered builds.'
                             .format(config.tag_prefix))
    parser.add_argument('--numbered-release-keep-count', type=int, default=0,
                        help='Number of numbered releases to keep. If set to 0, this check is disabled, otherwise if the number of numbered releases exceeds that number, '
                             'the oldest numbered release will be deleted. Note that due to a race condition of several Travis-CI builds running at the same time, '
                              'although unlikely, it\'s possible for the number of kept numbered releases to exceed that number by the number of concurrent Travis-CI builds running.')
    parser.add_argument('--numbered-release-keep-time', type=int, default=0,
                        help='How long to keep the numbered releases for, in seconds. If set to 0, this check is disabled, '
                             'otherwise all numbered releases that are older than the specified amount of seconds will be deleted.')
    parser.add_argument('--numbered-release-name', type=str, help='Release name text. If not specified a predefined text is used.')
    parser.add_argument('--numbered-release-body', type=str, help='Release body text. If not specified a predefined text is used.')
    parser.add_argument('--numbered-release-draft', default=False, action='store_true', help='Publish as a draft.')
    parser.add_argument('--numbered-release-prerelease', default=False, action='store_true', help='Publish as a prerelease.')
    parser.add_argument('--numbered-release-target-commitish', type=str,
                        help='Commit the release should point to. By default it\'s set to $TRAVIS_COMMIT when publishing to the same repo and not set when publishing to a different repo.')

def publish_validate_args(args):
    if not args.numbered_release:
        return False
    if args.numbered_release_keep_count < 0:
        raise exception.CIReleasePublisherError('--numbered-release-keep-count can\'t be set to a negative number.')
    if args.numbered_release_keep_time < 0:
        raise exception.CIReleasePublisherError('--numbered-release-keep-time can\'t be set to a negative number.')
    if args.numbered_release_keep_count == 0 and args.numbered_release_keep_time == 0:
        raise exception.CIReleasePublisherError('You must specify at least one of --numbered-release-keep-* options specifying the strategy for keeping numbered releases.')
    return True

def publish_with_args(args, releases, artifact_dir, github_api_url, travis_api_url, travis_url):
    if not args.numbered_release:
        return
    publish(releases, artifact_dir, args.numbered_release_keep_count, args.numbered_release_keep_time, args.numbered_release_name, args.numbered_release_body,
            args.numbered_release_draft, args.numbered_release_prerelease, args.numbered_release_target_commitish, github_api_url, travis_url)

def publish(releases, artifact_dir, numbered_release_keep_count, numbered_release_keep_time, numbered_release_name, numbered_release_body, numbered_release_draft, numbered_release_prerelease, numbered_release_target_commitish, github_api_url, travis_url):
    github_token        = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    github_repo_slug    = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')
    travis_repo_slug    = env.required('TRAVIS_REPO_SLUG')
    travis_branch       = env.required('TRAVIS_BRANCH')
    travis_commit       = env.required('TRAVIS_COMMIT')
    travis_build_number = env.required('TRAVIS_BUILD_NUMBER')
    travis_build_id     = env.required('TRAVIS_BUILD_ID')
    travis_tag          = env.optional('TRAVIS_TAG')

    if travis_tag:
        return
    tag_name = _tag_name(travis_branch, travis_build_number)
    logging.info('* Creating a numbered release with the tag name "{}".'.format(tag_name))
    _retention_policy(releases, numbered_release_keep_count, numbered_release_keep_time, github_token, github_api_url, github_repo_slug, travis_branch, travis_build_number)
    tag_name_tmp = _tag_name_tmp(travis_branch, travis_build_number)
    logging.info('Creating a numbered draft release with the tag name "{}".'.format(tag_name_tmp))
    release = github.github(github_token, github_api_url).get_repo(github_repo_slug).create_git_release(
        tag=tag_name_tmp,
        name=numbered_release_name if numbered_release_name else
             'CI build of {} branch #{}'.format(travis_branch, travis_build_number),
        message=numbered_release_body if numbered_release_body else
                'This is an auto-generated release based on [Travis-CI build #{}]({}/{}/builds/{})'
                .format(travis_build_id, travis_url, travis_repo_slug, travis_build_id),
        draft=True,
        prerelease=numbered_release_prerelease,
        target_commitish=numbered_release_target_commitish if numbered_release_target_commitish else travis_commit if not env.optional('CIRP_GITHUB_REPO_SLUG') else GithubObject.NotSet)
    github.upload_artifacts(artifact_dir, release)
    previous_release = [r for r in releases if r.tag_name == tag_name]
    if previous_release:
        logging.info('This job appers to have been restarted as "{}" release already exists.'.format(tag_name))
        github.delete_release_with_tag(previous_release[0], github_token, github_api_url, github_repo_slug)
    logging.info('Changing the tag name from "{}" to "{}"{}.'.format(tag_name_tmp, tag_name, '' if numbered_release_draft else ' and removing the draft flag'))
    release.update_release(name=release.title, message=release.body, prerelease=release.prerelease, target_commitish=release.target_commitish, draft=numbered_release_draft, tag_name=tag_name)

def cleanup(releases, branch_unfinished_build_numbers, github_api_url):
    github_token        = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    github_repo_slug    = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')
    travis_branch       = env.required('TRAVIS_BRANCH')
    travis_build_number = env.required('TRAVIS_BUILD_NUMBER')
    travis_tag          = env.optional('TRAVIS_TAG')

    if travis_tag:
        return
    logging.info('* Deleting incomplete numbered releases left over due to jobs failing or being cancelled.')
    # FIXME(nurupo): once Python 3.8 is out, use Assignemnt Expression to prevent expensive _break_tag_name() calls https://www.python.org/dev/peps/pep-0572/
    numbered_releases_incomplete = [r for r in releases if r.draft and
                                    _break_tag_name_tmp(r.tag_name) and
                                    _break_tag_name_tmp(r.tag_name)['branch'] == travis_branch and
                                    (
                                        (int(_break_tag_name_tmp(r.tag_name)['build_number']) == int(travis_build_number)) or
                                        (
                                            (int(_break_tag_name_tmp(r.tag_name)['build_number']) < int(travis_build_number)) and
                                            (_break_tag_name_tmp(r.tag_name)['build_number'] not in branch_unfinished_build_numbers)
                                        )
                                    )]
    numbered_releases_incomplete = sorted(numbered_releases_incomplete, key=lambda r: int(_break_tag_name_tmp(r.tag_name)['build_number']))
    for r in numbered_releases_incomplete:
        try:
            github.delete_release_with_tag(r, github_token, github_api_url, github_repo_slug)
        except Exception as e:
            logging.warning('{}: {}'.format(type(e).__name__, e))
