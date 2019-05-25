# -*- coding: utf-8 -*-

from github import GithubObject
import logging
import re

from . import config
from . import env
from . import exception
from . import github
from . import travis

_tmp_tag_suffix = 'tag'

def _tag_name(travis_tag):
    return '{}'.format(travis_tag)

def _break_tag_name(tag_name):
    return {'tag': tag_name}

def _tag_name_tmp(travis_tag):
    return '{}{}-{}-{}'.format(config.tag_prefix_tmp, config.tag_prefix, _tag_name(travis_tag), _tmp_tag_suffix)

def _break_tag_name_tmp(tag_name):
    prefix = '{}{}'.format(config.tag_prefix_tmp, config.tag_prefix)
    if not tag_name.startswith(prefix) or not tag_name.endswith(_tmp_tag_suffix):
        return None
    tag_name = tag_name[len(prefix):-len(_tmp_tag_suffix)]
    if not tag_name.startswith('-') or not tag_name.endswith('-'):
        return None
    tag_name = tag_name[1:-1]
    return _break_tag_name(tag_name)

def publish_args(parser):
    parser.add_argument('--tag-release', default=False, action='store_true',
                        help='Publish a release for a pushed tag. A separate "<tag>" release will be made whenever a tag is pushed.')
    parser.add_argument('--tag-release-name', type=str, help='Release name text. If not specified a predefined text is used.')
    parser.add_argument('--tag-release-body', type=str, help='Release body text. If not specified a predefined text is used.')
    parser.add_argument('--tag-release-draft', default=False, action='store_true', help='Publish as a draft.')
    parser.add_argument('--tag-release-prerelease', default=False, action='store_true', help='Publish as a prerelease.')
    parser.add_argument('--tag-release-target-commitish', type=str,
                        help='Commit the release should point to. By default it\'s set to $TRAVIS_COMMIT when publishing to the same repo and not set when publishing to a different repo.')
    parser.add_argument('--tag-release-force-recreate', default=False, action='store_true',
                        help='Force recreation of the release if it already exists. DANGER. You almost never want to enable this option. '
                             'When enabled, your existing tag release will be deleted, all of its text and artifacts will be forever lost, '
                             'and a new tag release will be created based on this build. '
                             'Note that by enabling this, someone might accidentally (or not) restart a tag release build on Travis-CI, '
                             'causing the release to be recreated. You have been warned.')

def publish_validate_args(args):
    return args.tag_release

def publish_with_args(args, releases, artifact_dir, github_api_url, travis_api_url, travis_url):
    if not args.tag_release:
        return
    publish(releases, artifact_dir, args.tag_release_name, args.tag_release_body, args.tag_release_draft, args.tag_release_prerelease,
            args.tag_release_target_commitish, args.tag_release_force_recreate, github_api_url, travis_api_url, travis_url)

def publish(releases, artifact_dir, tag_release_name, tag_release_body, tag_release_draft, tag_release_prerelease, tag_release_target_commitish, tag_release_force_recreate, github_api_url, travis_api_url, travis_url):
    github_token        = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    github_repo_slug    = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')
    travis_repo_slug    = env.required('TRAVIS_REPO_SLUG')
    travis_commit       = env.required('TRAVIS_COMMIT')
    travis_build_number = env.required('TRAVIS_BUILD_NUMBER')
    travis_build_id     = env.required('TRAVIS_BUILD_ID')
    travis_tag          = env.optional('TRAVIS_TAG')

    if not travis_tag:
        return
    tag_name = _tag_name(travis_tag)
    logging.info('* Creating a tag release with the tag name "{}".'.format(tag_name))

    def _is_latest_build_for_branch():
        if int(travis.Travis.github_auth(github_token, travis_api_url).branch_last_build_number(travis_repo_slug, travis_tag)) == int(travis_build_number):
            return True
        logging.info('Not creating the "{}" release because this is not the latest build for the "{}" tag.'.format(tag_name, travis_tag))
        return False

    if not _is_latest_build_for_branch():
        return
    tag_name_tmp = _tag_name_tmp(travis_tag)
    logging.info('Creating a release with the tag name "{}".'.format(tag_name_tmp))
    release = github.github(github_token, github_api_url).get_repo(github_repo_slug).create_git_release(
        tag=tag_name_tmp,
        name=tag_release_name if tag_release_name else tag_name,
        message=tag_release_body if tag_release_body else
                'This is an auto-generated release based on [Travis-CI build #{}]({}/{}/builds/{})'
                .format(travis_build_id, travis_url, travis_repo_slug, travis_build_id),
        draft=True,
        prerelease=tag_release_prerelease,
        target_commitish=tag_release_target_commitish if tag_release_target_commitish else travis_commit if not env.optional('CIRP_GITHUB_REPO_SLUG') else GithubObject.NotSet)
    github.upload_artifacts(artifact_dir, release)
    if not _is_latest_build_for_branch():
        github.delete_release_with_tag(release, github_token, github_api_url, github_repo_slug)
        return
    previous_release = [r for r in releases if r.tag_name == tag_name]
    if previous_release:
        if tag_release_force_recreate:
            # Delete release but keep the tag, since in Tag Releases the user creates the tag, not us
            logging.info('Deleting a release with the tag name "{}".'.format(tag_name))
            previous_release[0].delete_release()
        else:
            github.delete_release_with_tag(release, github_token, github_api_url, github_repo_slug)
            raise exception.CIReleasePublisherError('Tag release with the tag name "{}" already exists. Are you sure you meant to recreate the tag release? '
                                                    'Recreating a publicly visible tag release might be disastrous, as all the changes you have done to the release -- changed text, '
                                                    'extra artifacts and so on -- will be lost, as well as hashes of the files created as part of the build might change. '
                                                    'Please manually delete the "{}" release and restart the build if you really meant to recreate the release.'.format(tag_name, tag_name))
    logging.info('Changing the tag name from "{}" to "{}"{}.'.format(tag_name_tmp, tag_name, '' if tag_release_draft else ' and removing the draft flag'))
    release.update_release(name=release.title, message=release.body, prerelease=release.prerelease, target_commitish=release.target_commitish, draft=tag_release_draft, tag_name=tag_name)

def cleanup(releases, branch_unfinished_build_numbers, github_api_url):
    github_token        = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
    github_repo_slug    = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')
    travis_build_number = env.required('TRAVIS_BUILD_NUMBER')
    travis_tag          = env.optional('TRAVIS_TAG')

    if not travis_tag:
        return
    logging.info('* Deleting incomplete tag releases left over due to jobs failing or being cancelled.')
    # FIXME(nurupo): once Python 3.8 is out, use Assignemnt Expression to prevent expensive _break_tag_name() calls https://www.python.org/dev/peps/pep-0572/
    tag_releases_incomplete = [r for r in releases if r.draft and
                               _break_tag_name_tmp(r.tag_name) and
                               _break_tag_name_tmp(r.tag_name)['tag'] == travis_tag]
    if not tag_releases_incomplete or any(n != travis_build_number for n in branch_unfinished_build_numbers):
        return
    for r in tag_releases_incomplete:
        try:
            github.delete_release_with_tag(r, github_token, github_api_url, github_repo_slug)
        except Exception as e:
            logging.warning('{}: {}'.format(type(e).__name__, e))
