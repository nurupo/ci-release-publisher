#!/usr/bin/env bash

set -euo pipefail

. .travis/cirp/check_precondition.sh

if [ ! -z "$TRAVIS_TEST_RESULT" ] && [ "$TRAVIS_TEST_RESULT" != "0" ]; then
  echo "Build has failed, skipping publishing"
  exit 0
fi

if [ "$#" != "1" ]; then
  echo "Error: No arguments provided. Please specify a directory where to download artifacts to as the first argument."
  exit 1
fi

ARTIFACTS_DIR="$1"

. .travis/cirp/install.sh

ci-release-publisher collect "$ARTIFACTS_DIR"
