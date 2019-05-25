# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys

from . import config
from . import env
from . import exception
from . import github
from . import latest_release, numbered_release, tag_release
from . import temporary_store_release
from . import travis
from .__version__ import __description__, __title__, __version__

def main():
    try:
        logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO, datefmt='%H:%M:%S')

        release_kinds = [latest_release, numbered_release, tag_release]

        parser = argparse.ArgumentParser(description=__description__)
        parser.add_argument('--version', action='version', version='%(prog)s {}'.format(__version__))

        # Travis
        parser_travis = parser.add_mutually_exclusive_group()
        parser_travis.add_argument('--travis-instance-org', dest='travis_type', action='store_const', const='org',
                                    help='Use API of the https://travis-ci.org instance.')
        parser_travis.add_argument('--travis-instance-com', dest='travis_type', action='store_const', const='com',
                                    help='Use API of the https://travis-ci.com instance.')
        parser_travis.add_argument('--travis-instance-custom', dest='travis_type', metavar='TRAVIS_URL', type=str,
                                    help='Use API of Travis-CI running under a personal domain. Specify the Travis-CI instance URL, not the API endpoint URL, e.g. "https://travis.example.com".')
        parser.set_defaults(travis_type='com')

        parser.add_argument('--github-api-url', type=str, default="",
                            help='Use custom GitHib API URL, e.g. for self-hosted GitHub Enterprise instance. Should be an URL to the API endpoint, e.g. "https://api.github.com".')

        parser.add_argument('--tag-prefix', type=str, default=config.tag_prefix, help='git tag prefix to use when creating releases.')
        parser.add_argument('--tag-prefix-incomplete-releases', type=str, default=config.tag_prefix_tmp, dest='tag_prefix_tmp',
                            help='An additional git tag prefix, on top of the existing one, to use for indicating incomplete, in-progress releases.')

        subparsers = parser.add_subparsers(dest='command')

        # store subparser
        parser_store = subparsers.add_parser('store', help='Store artifacts of the current job in a draft release for the later collection by a job calling the "publish" command.')
        parser_store.add_argument('artifact_dir', metavar='ARTIFACT_DIR', help='Path to a directory containing artifacts that need to be stored.')
        temporary_store_release.publish_args(parser_store)

        # cleanup store subparser
        parser_cleanup_store = subparsers.add_parser('cleanup_store', help='Delete the releases created by the "store" command.')
        temporary_store_release.cleanup_args(parser_cleanup_store)

        # collect subparser
        parser_collect = subparsers.add_parser('collect', help='Collect artifacts from all draft releases created by the "store" command during the current build in a directory.')
        parser_collect.add_argument('artifact_dir', metavar='ARTIFACT_DIR', help='Path to a directory where artifacts should be collected to.')

        # publish subparser
        parser_publish = subparsers.add_parser('publish', help='Publish releases with artifacts from a directory.')
        parser_publish.add_argument('artifact_dir', metavar='ARTIFACT_DIR', help='Path to a directory containing build artifacts to publish.')

        # cleanup publish subparser
        parser_cleanup_publish = subparsers.add_parser('cleanup_publish', help='Delete incomplete releases left over by the "publish" command by the current and previous builds.')

        for r in release_kinds:
            r.publish_args(parser_publish)

        args = parser.parse_args()

        # Sanity-check arguments

        travis_url = args.travis_type
        travis_api_url = '{}/api'.format(travis_url)
        if args.travis_type == 'org':
            travis_url = 'https://travis-ci.org'
            travis_api_url = 'https://api.travis-ci.org'
        elif args.travis_type == 'com':
            travis_url = 'https://travis-ci.com'
            travis_api_url = 'https://api.travis-ci.com'

        if not args.github_api_url:
            args.github_api_url = "https://api.github.com"

        try:
            if not args.tag_prefix:
                raise exception.CIReleasePublisherError('--tag-prefix can\'t be empty.')
            if not args.tag_prefix_tmp:
                raise exception.CIReleasePublisherError('--tag-prefix-incomplete-releases can\'t be empty.')
            config.tag_prefix = args.tag_prefix
            config.tag_prefix_tmp = args.tag_prefix_tmp

            github_token     = env.required('CIRP_GITHUB_ACCESS_TOKEN') if env.optional('CIRP_GITHUB_ACCESS_TOKEN') else env.required('GITHUB_ACCESS_TOKEN')
            github_repo_slug = env.required('CIRP_GITHUB_REPO_SLUG') if env.optional('CIRP_GITHUB_REPO_SLUG') else env.required('TRAVIS_REPO_SLUG')

            if args.command == 'store':
                if not os.path.isdir(args.artifact_dir):
                    raise exception.CIReleasePublisherError('Directory "{}" doesn\'t exist.'.format(args.artifact_dir))
                if len(os.listdir(args.artifact_dir)) <= 0:
                    raise exception.CIReleasePublisherError('No artifacts found in "{}" directory.'.format(args.artifact_dir))
                releases = github.github(github_token, args.github_api_url).get_repo(github_repo_slug).get_releases()
                temporary_store_release.publish_with_args(args, releases, args.artifact_dir, args.github_api_url, travis_api_url, travis_url)
            elif args.command == 'cleanup_store':
                releases = github.github(github_token, args.github_api_url).get_repo(github_repo_slug).get_releases()
                temporary_store_release.cleanup_with_args(args, releases, args.github_api_url, travis_api_url)
            elif args.command == 'collect':
                if not os.path.isdir(args.artifact_dir):
                    raise exception.CIReleasePublisherError('Directory "{}" doesn\'t exist.'.format(args.artifact_dir))
                releases = github.github(github_token, args.github_api_url).get_repo(github_repo_slug).get_releases()
                temporary_store_release.download(releases, args.artifact_dir)
            elif args.command == 'publish':
                if not os.path.isdir(args.artifact_dir):
                    raise exception.CIReleasePublisherError('Directory "{}" doesn\'t exist.'.format(args.artifact_dir))
                if len(os.listdir(args.artifact_dir)) <= 0:
                    raise exception.CIReleasePublisherError('No artifacts found in "{}" directory.'.format(args.artifact_dir))
                if not any(r.publish_validate_args(args) for r in release_kinds):
                    raise exception.CIReleasePublisherError('You must specify what kind of release you would like to publish.')
                releases = github.github(github_token, args.github_api_url).get_repo(github_repo_slug).get_releases()
                for r in release_kinds:
                    r.publish_with_args(args, releases, args.artifact_dir, args.github_api_url, travis_api_url, travis_url)
            elif args.command == 'cleanup_publish':
                releases = github.github(github_token, args.github_api_url).get_repo(github_repo_slug).get_releases()
                branch_unfinished_build_numbers = travis.Travis.github_auth(github_token, travis_api_url).branch_unfinished_build_numbers(env.required('TRAVIS_REPO_SLUG'), env.required('TRAVIS_BRANCH'))
                for r in release_kinds:
                    r.cleanup(releases, branch_unfinished_build_numbers, args.github_api_url)
            else:
                raise exception.CIReleasePublisherError('Specify one of "store", "cleanup_store", "collect", "publish" or "cleanup_publish" commands.')
        except exception.CIReleasePublisherError as e:
            logging.error('Error: {}'.format(str(e)))
            sys.exit(1)
    except Exception as e:
        # We are removing stack traces from all uncaught exceptions, which should prevent API key leakage
        logging.error('{}: {}'.format(type(e).__name__, e))
        sys.exit(1)

if __name__ == '__main__':
    main()
