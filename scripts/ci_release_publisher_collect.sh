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

if [ -z "$ARTIFACTS_DIR" ]; then
  echo "Error: Environment varialbe ARTIFACTS_DIR is not set."
  exit 1
fi

pip install ci_release_publisher
ci-release-publisher collect "$ARTIFACTS_DIR"
