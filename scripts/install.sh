# Install verifying the hash

# Verifying PGP signture on CI is error-prone, keyservers often fail to return
# the key and even if they do, `gpg --verify` returns success with a revoked
# or expired key. Thus it's probably better to verify the signature yourself,
# on your local machine, and then rely on the hash on the CI.

# Set the variables below for the version of ci_release_publisher you would like
# to use. The set values are provided as an example.
#VERSION="0.1.0rc1"
#FILENAME="ci_release_publisher-$VERSION-py3-none-any.whl"
#HASH="5a7f0ad6ccfb6017974db42fb1ecfe8b3f9cc1c16ac68107a94979252baa16e3"

# Get Python >=3.5
if [ "$TRAVIS_OS_NAME" == "osx" ]; then
  brew update

  # Upgrade Python 2 to Python 3
  brew upgrade python || true

  # Print python versions
  python --version || true
  python3 --version || true
  pyenv versions || true

  cd .
  cd "$(mktemp -d)"
  virtualenv env -p python3
  set +u
  source env/bin/activate
  set -u
  cd -

  # make sha256sum available
  export PATH="/usr/local/opt/coreutils/libexec/gnubin:$PATH"
elif [ "$TRAVIS_OS_NAME" == "linux" ]; then
  # Print python versions
  python --version || true
  python3 --version || true
  pyenv versions || true

  pyenv global 3.6
fi

pip install --upgrade pip

check_sha256()
{
  if ! ( echo "$1  $2" | sha256sum -c --status - ); then
    echo "Error: sha256 of $2 doesn't match the known one."
    echo "Expected: $1  $2"
    echo -n "Got: "
    sha256sum "$2"
    exit 1
  else
    echo "sha256 matches the expected one: $1"
  fi
}

# Don't install again if already installed.
# OSX keeps re-installing it tough, as it uses a temp per-script virtualenv.
if ! pip list --format=columns | grep '^ci-release-publisher '; then
  cd .
  cd "$(mktemp -d)"
  pip download ci_release_publisher==$VERSION
  check_sha256 "$HASH" "$FILENAME"
  pip install --no-index --find-links "$PWD" "$FILENAME"
  cd -
fi
