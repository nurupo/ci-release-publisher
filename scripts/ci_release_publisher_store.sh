#!/usr/bin/env bash

set -euo pipefail

if [ ! -z "$TRAVIS_PULL_REQUEST" ] && [ "$TRAVIS_PULL_REQUEST" != "false" ]; then
  echo "Skipping publishing in a Pull Request"
  exit 0
fi

if [ ! -z "$TRAVIS_TEST_RESULT" ] && [ "$TRAVIS_TEST_RESULT" != "0" ]; then
  echo "Build has failed, skipping publishing"
  exit 0
fi

if [ "$#" != "1" ]; then
  echo "Error: No arguments provided. Please specify a directory containing artifacts as the first argument."
  exit 1
fi

ARTIFACTS_DIR="$(readlink -f -- $1)"

pip install ci_release_publisher
ci-release-publisher store "$ARTIFACTS_DIR"
