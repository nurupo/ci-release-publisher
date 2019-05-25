#!/usr/bin/env bash

set -euo pipefail

if [ ! -z "$TRAVIS_PULL_REQUEST" ] && [ "$TRAVIS_PULL_REQUEST" != "false" ]; then
  echo "Skipping publishing in a Pull Request"
  exit 0
fi

if [ -z "$TRAVIS_TEST_RESULT" ] && [ "$TRAVIS_TEST_RESULT" == "0" ]; then
  echo "Build has not failed, skipping cleanup"
  exit 0
fi

pip install ci_release_publisher
ci-release-publisher cleanup_publish
ci-release-publisher cleanup_store --scope current-build previous-finished-builds \
                                   --release complete incomplete
