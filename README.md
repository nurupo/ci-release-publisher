# CI Release Publisher

A script for publishing Travis-CI build artifacts on GitHub Releases.

Mainly geared towards publishing nightly/continuous builds, which Travis-CI has no native support of, but can also be used to publish release builds.

## Table of contents

- [Features](#features)
- [Terminology](#terminology)
- [CI Release Publisher vs. Travis-CI's GitHub Releases deployment](#ci-release-publisher-vs-travis-cis-github-releases-deployment)
  - [Short comparison](#short-comparison)
  - [Detailed comparison](#detailed-comparison)
- [Handling race conditions](#handling-race-conditions)
- [Installation](#Installation)
  - [Signatures](#signatures)
- [Usage](#usage)
  - [Security consideration](#security-consideration)
  - [Publishing to the same repository](#publishing-to-the-same-repository)
  - [Publishing to a different repository](#publishing-to-a-different-repository)
  - [Doing everything in a different repository](#doing-everything-in-a-different-repository)
- [Command line arguments](#command-line-arguments)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- Two flavors of a nightly/continuous release:
  - **Latest Release**: a `ci-<branch>-latest` tagged release that will be kept updated to contain build artifacts of the latest Travis-CI build for the branch
  - **Numbered Release**: a `ci-<branch>-<build-number>` tagged release that will contain build artifacts of `<build-number>` Travis-CI build for the branch
    - Retention policies for Numbered Releases:
        - Keep only the last N numbered releases for the branch, extra numbered releases will be deleted starting with the lowest `<build-number>` first (i.e. oldest release first)
        - Keep only numbered releases that were published within the last N seconds (i.e. delete all numbered releases older than N seconds)
- **Tag Release**: a regular release that is made only on a tag push
- Customize release information of each of the three release types independently:
  - Release name
  - Release body (e.g. set it to a list of hashes of all build artifacts)
  - Draft flag (e.g. if you want the releases to be private)
  - Pre-release flag (e.g. when every nightly is a production release!)
  - Target commit
- Race condition proof - no matter how many builds or jobs per build you have running in parallel, no release will get corrupted due to a race condition
- Allows publishing to a different GitHub repository's Releases page
- Supports public GitHub repos (tested), but should also work with private GitHub repos and self-hosted GitHub instances (both are not tested)

## Terminology

Let's define some terms we will use throughout this file, things might get confusing if you don't know them.

### CI Release Publisher terms

See **Latest Release**, **Numbered Release** and **Tag Release** in [Features](#features).

### Travis-CI terms

**Job** - A single process consisting of git cloning your repository and then running arbitrary commands on the machine, usually to build and/or test the software that is in the repository.

**Stage** - A set of jobs. Stages allow to enforce job execution order. All jobs within a stage run in parallel, however each stage runs sequentially, e.g. jobs in stage2 won't start running until all of the jobs in stage1 complete. This feature also sometimes called Pipeline, for example in GitLab CI.

**Build** - A set of stages. If at least one job in a builds fails - the build gets marked as failed. Builds are created whenever you push to a GitHub repository that has Travis-CI configured for it. In a very minimal case a build has just one stage with one job in it.

Here is an example of a build having 5 stages and 15 jobs: [url](https://travis-ci.org/qTox/qTox/builds/406143072), [screenshot](https://i.imgur.com/K1hAR9R.png).

### GitHub terms

**Release** - A feature allowing to associate downloadable files with an existing git tag. Mainly used for distributing the software and software-related files. All releases can be viewed on a dedicated Releases page of a GitHub repository, on which releases are ordered by their creation time.

**Draft Release** - A release that is "private", i.e. visible only to people who have priviliged access to the repository (Write or Admin repository permissions). A draft release can be changed to a non-draft release, making it public and creating a git tag for it if it didn't exist before.

**Pre-release Release** - A release that is visibly marked as not production-ready. Ideal for nightly/continuous releases.

## CI Release Publisher vs. Travis-CI's GitHub Releases deployment

Travis-CI provides [GitHub Releases deployment option](https://docs.travis-ci.com/user/deployment/releases/) that many are familiar with, so let's make a quick comparison of how CI Release Publisher differs from Travis-CI's deployment option.

### Short comparison

Here is a table summarizing the comparison if you don't want to read through it.

| Features                         | CI Release Publisher  | Travis-CI             |
|----------------------------------|-----------------------|-----------------------|
| Tag Release                      | yes                   | yes                   |
| Latest Release                   | yes                   | no*                   |
| Numbered Releases                | yes                   | no                    |
| Customizable release information | yes                   | yes**                 |
| Race condition proof             | yes                   | no                    |
| Proper draft releases            | yes                   | no                    |

`*` -- can be done [with some extra bash commands](https://github.com/travis-ci/travis-ci/issues/8622#issuecomment-354912673), but is not part of Travis-CI's GitHub Releases deployment feature set and also won't be race condition proof.

`**` -- Travis-CI's release body [can't contain new lines](https://github.com/travis-ci/dpl/issues/155), so you can't include multiline changelog in it, which means that you wouldn't be able to list hashes of artifacts, for example.

### Detailed comparison

Travis-CI's GitHub Releases deployment option works great for non-draft Tag Releases. In fact, if that's all you need, then you should strongly consider using Travis-CI's GitHub Releases deployment option over CI Release Publisher, as Travis-CI provides about the same amount of release customization as CI Release Publisher (sans the support of new lines in the release body).

However, on this the usefulness of Travis-CI's GitHub Releases deployment ends. Travis-CI falls short if you want to set a release body containing new lines, create a race condition proof Tag Release, create any kind of draft release, create a Latest Release, or create a Numbered Release.

#### New lines in release body

Travis-CI doesn't support new lines when specifying release's body [due to Travis-CI's component handling deployment having problems with new lines](https://github.com/travis-ci/dpl/issues/155). CI Release Publisher doesn't have this limitation.

#### Tag Release

Travis-CI's Tag Releases are not race condition proof. You can push a tag to GitHub, which will create a Travis-CI build, then delete the tag and push it again, supposedly pointing to some new fixup commit this time around, which will create another Travis-CI build. You will now have two Travis-CI builds running in parallel and uploading artifacts to the same tag release, which is a race condition. You might end up with a release some artifacts of which come from the first build and some from the second build which has the fix you pushed. CI Release Publisher doesn't have this issue, it makes sure that a Tag Release will contain artifacts only from the latest build for that tag.

#### Draft release

The issue with Travis-CI's draft releases is that while for non-draft releases Travis-CI creates just a single release for the whole build containing artifacts of all jobs, which is what you want, for draft releases Travis-CI instead creates numerous draft releases, one for every single job in the build, which is not you want. For example, if you have 10 jobs then you will get 10 draft releases, each containing artifacts of only that one particular job, when you actually expected to get just one draft release containing artifacts of all the 10 jobs. Just changing `draft: false` to `draft: true` in Travis-CI changes the behaviour so drastically. CI Release Publisher has no such issue, it creates just one final release containing artifacts of all jobs, both when creating draft and non-draft releases.

#### Latest Release

As far as the issue with Latest Release goes, Travis-CI's GitHub Releases deployment simply doesn't support creating such releases. There is no option for it. There is, however, [a workaround](https://github.com/travis-ci/travis-ci/issues/8622#issuecomment-354912673) that allows to achieve creating Latest Release on Travis-CI, but it requires running some additional bash/git commands and has a race condition that might result in a release being corrupted, i.e. it allows several builds editing the same release at the same time. CI Release Publisher supports creating Latest Release and it does so without race conditions.

#### Numbered Release

Travis-CI doesn't support creating Numbered Releases either. Although you could create them with the same workaround that you can use to create Latest Release, there is no easy way to delete previous Numbered Releases without using GitHub API. If you think you could avoid using GitHub API by expanding the workaround to use `git` command line program to delete git tags in order to delete releases -- that wouldn't work, if a git tag of a GitHub release is deleted the release doesn't get deleted, it remains but changes to a draft. There would also be a race condition with deleting previous Numbered Releases this way as they might still be in the process of being created by another builds as you delete them, which might result in those builds creating incomplete releases. To do it properly you'd need to essentially re-invent CI Release Publisher.

## Handling race conditions

Special care was taken to make sure that CI Release Publisher avoids race conditions, especially the ones that can corrupt a release -- result in a release that doesn't contain all of the artifacts, or a release in which some artifacts come from one build, and thus one commit, but other from another. This section will talk about CI Release Publisher features, about how, if implemented naively, they would have race conditions, and how does CI Release Publisher avoid those race conditions. This is not a complete list of the race conditions CI Release Publisher has to deal with, but it gives a good idea about how CI Release Publisher works.

There are two primary points at which race conditions can occur: when jobs run in parallel and when builds run in parallel. We consider only the builds within the same branch/tag as in CI Release Publisher builds from different branches/tags can't affect each other.

### Jobs running in parallel

The goal of CI Release Publisher is to create a release containing artifacts of a all artifact-producing jobs for a build. A naive way to do so would be to make jobs create a GitHub release, let them upload their artifacts into it and that's it, done -- we would have a single release with all jobs' artifacts.

While this naive implementation would work if jobs execute sequentially, it has a race condition when two or more jobs run in parallel and they try to create a GitHub release. The jobs would check GitHub API to see if some other job from this build has already created a release which should be used instead of creating a new one, but because they can check it all at the same time, multiple jobs can end up seeing that no other job has created a release yet and decide to create one, which will result in multiple releases being created for this build, with build artifacts divided among them. Multiple releases being created for a single build is definitely not what we want, and there is no easy way to prevent it. GitHub API happily creates as many instances of identical draft releases as you ask it to, without raising any errors, so we can't use GitHub API as a race gate keeper that will pass only the the first job trying to create a release and reject all other.

CI Release Publisher solves this issue by serializing the creation of the release for the build, it makes it so that only one job is responsible for creating the release, but this comes at the cost of having a separate Stage in the build. CI Release Publisher makes each artifact-producing job create a unique temporary store release containing build artifacts of just that job, and then, in the following Stage, it collects all of those artifacts from the temporary store releases, deletes those releases, and creates a proper release containing all of those artifacts. That way there is only one job that creates the (final) release and thus no race condition can occur as it's not racing with anyone.

While this successfully solves the race issue, it has a slight disadvantage. If the build fails before it reaches the publishing stage, all those temporary store releases won't be deleted and would litter the Releases page, though only repo admins can see draft releases listed on it. This is mostly solved by making jobs before the publishing stage check if the build is failing and deleting those releases, that way we don't have to rely solely on the publishing stage to remove them.

### Builds running in parallel

The main issue with builds running in parallel is that it's possible for several builds to modify the same release at the same time.

#### Latest Release

A Latest Release is a release containing the artifacts of the latest build for a branch. A Latest Release always has the same `ci-<branch>-latest` tag name, so you can easily link to it in README or on website, since the URL won't change. There is always no more than one Latest Release per branch. A naive implementation of the Latest Release feature would be to make each build delete the existing Latest Release, if any, and create a new one with current build's artifacts.

This naive implementation would work if builds are executed sequentially, but it has a race condition when two or more builds run in parallel and they try to delete and create the Latest Release. There are several thing that can go wrong. Firstly, we can have one build deleting a release that another build might be in the process of uploading artifacts to, which will make the uploading build throw an exception and fail -- and rightfully so, as we consider a release that has artifacts missing a failure. Secondly, we can have a situation when the newer build finishes earlier than the older one due to code changes or removal of some build steps, which will result in the older build being the last one to delete and then re-create Latest Release, meaning that the Latest Release will contain artifacts of the older build instead of the newer one.

CI Release Publisher solves this issue by updating (deleting and then re-creating) the Latest Release only if the current build is the latest build for the branch. It checks Travis-CI API to get the build number of the latest build for the branch, and if it's not the build number of the current build, it skips updating the Latest Release, leaving it to a newer build instead. This way only one build modifies the Latest Release -- the modification is serialized. This solves both the first and the second of the mentioned issues. It additionally protects Latest Release against being downgraded to contain artifacts of an older build when someone restarts an old Travis-CI build.

The downside of this solution is, paradoxically, that only the latest build can update the Latest Release. In a situation when you have multiple builds running in parallel, with all but the latest succeeding, all those succeeded builds will pass on updating the Latest Release, leaving it up to the latest build, but because that build has failed, it won't reach the publishing Stage and won't update any releases, so you will end up with the Latest Release not being updated at all. There is no workaround for this, so just try to make sure that your builds don't fail and follow up a failed build with a fixed one.

By the way, you might notice that this solution still leaves out a race condition, specifically the case of when a new build gets created right after the older build checks Travis-CI API to make sure that it's the latest build for the branch -- this could lead to both builds updating the Latest Release as both will think that they are the latest builds. However, such race condition is ruled out as impossible, as it takes just a couple of GitHub API calls, literally less than a second, for the older build to update the Latest Release after checking with Travis-CI API. All it has to do is 1) call GitHub API to delete the previous latest release and 2) call the GitHub API again to change the tag name of an already created release with all artifacts already uploaded to the proper Latest Release tag name. The newly created build likely hasn't even started yet, more so got to the release publishing Stage, to the point where it updates Latest Release, in such short time. So there should be no chance of the both builds updating the release at the same time.

#### Tag Release

Tag Release is implemented very similarly to Latest Release and doesn't deal with any new race condition issues, so there is nothing really to say about it.

#### Numbered Release

A Numbered Release is a release containing the artifacts of a specific build. Numbered Releases use `ci-<branch>-<build-number>` tag name, so unlike Latest Release, the release URL is always different. Numbered Releases have a retention policy options that dictate when existing Numbered Releases should be deleted. A naive implementation for the Numbered Release feature would be to make each build create a new Numbered Release for this build and delete existing Numbered Releases that are subject to deletion by the retention policy.

This naive implementation would work if builds are executed sequentially, but it has a race condition when two or more builds run in parallel, as an old build might be still in the process of uploading artifacts to its Numbered Release when a new build deletes that release, causing the older build to error due to it unable to upload the rest of the artifacts to a no longer existing release, which will cause the old build to fail.

CI Release Publisher solves this issue by executing the retention policy only on finished releases. It can do so because it can distinguish between in-progress and finished releases. When a release is just created, it has a special tag name indicating that it's in progress, and once all work on it is done, it gets renamed to a proper tag name. CI Release Publisher ignores all in-progress releases as not to fail the builds still working on them, considering only finished releases. This is no just a Numbered Release thing, CI Release Publisher does it for all of the release types, but it's especially important in Numbered Releases case. It also allows the repository owners to see which automated releases were completed and which are still in progress or failed without ever completing.

There are several downsides to this solution. Firstly, if the publishing job fails or gets canceled in the middle of running it's possible for it to leave an in-progress draft release, littering the Releases page. This issue is solved by adding additional cleanup code that removes existing in-progress releases if the corresponding builds are no longer running, according to Travis-CI API. Secondly, due to the retention policy considering only finished releases, the in-progress releases will slip past the retention policy. For example, if there are N builds running in parallel, all having in-progress releases, and the retention policy is set to keep at most M latest Numbered Releases, those N in-progress releases will slip past the retention policy, resulting in N+M Numbered Releases being kept. There is no solution for this issue. In practice this is not a big issue, as the N in practice tends to be rather small, often even zero, and the next build is going to execute the retention policy and delete any extra Numbered Releases, keeping only M in place.

## Installation

Make sure you use Python 3.5 or higher.

From source:

```bash
python setup.py install
```

From PyPi:

```bash
pip install ci_release_publisher
```

### Signatures

PyPi packages are PGP signed with a subkey of the following primary key:

```
Key fingerprint = 1D4E 9375 AD9B D50F 80FF  55AC 6F55 0977 4B1E F0C2
```

The signatures are uploaded to PyPi. Note that `pip` doesn't verify signatures, you have to do so manually. Also, PyPi website [hides the signature files from the download list on purpose](https://github.com/pypa/warehouse/issues/3356), so to get the signature files you have to append `.asc` at the end of download URLs.

You can download the package, verify its signature and install with something like the following:

```bash
wget "$(pip download ci_release_publisher | grep 'http.*ci_release_publisher-' | awk '{print $NF}').asc"
gpg --no-default-keyring --keyring "$PWD/tmp_keyring.gpg" --recv-key '1D4E 9375 AD9B D50F 80FF  55AC 6F55 0977 4B1E F0C2'
gpg --no-default-keyring --keyring "$PWD/tmp_keyring.gpg" --verify ci_release_publisher-*.asc
# Read the output of the command above, you can't rely on its exit code as it's
# 0, i.e. success, even if the key has expired or has been revoked
rm ci_release_publisher-*.asc
rm tmp_keyring.gpg
pip install --no-index --find-links "$PWD" ci_release_publisher-*
```

Of course that won't verify any of the dependencies CI Release Publisher is using.

## Usage

### Security consideration

Before using CI Release Publisher, you must consider the security implications that come with using it.

In order to use CI Release Publisher, you must create a new GitHub user, make that user a collaborator in a repository you wish to publish releases to, giving the user Write/push access to the repository which is required to create releases, generate an access token for that user and store it in an environment variable on Travis-CI. All of this is needed so that the CI Release Publisher script would be able to authenticate as the user with GitHub API and create releases in the desired repository.

The issue is that if the access token gets leaked, someone could use it to push code into the repository, delete/edit issue comments, push into PR branches, replace release files with malicious binaries, etc. -- do all kinds of nasty things. GitHub doesn't provide much in terms of restricting what an access token can be used for.

There are primary three different ways to use CI Release Publisher based on the security risk you are willing to take:

- Publishing to the same repository

    This is the same way Travis-CI's GitHub Releases deployment works. Travis-CI stores the access token for the main repository with the full write access to it. This represents the greatest security risk, since if the token is leaked, your main repository is at risk. If you already use such access token for some other Travis-CI automation -- you are already exposed to this risk.

- Publishing to a different repository

    Building still happens on Travis-CI of the main repository, but the build artifacts are published to a different repository. Travis-CI stores the access token with the full write access to the other repository now. This lowers the security risk considerably, since if the access token is leaked only the other repository would be affected by it, the main repository would be safe.

- Doing everything in a different repository

    Building happens on Travis-CI of the repository other than the main one and the build artifacts are published into the same other repository. The whole process is separate from the main repository and can be used to setup personal builds of other projects. This lowers the risk even further than just publishing to a different repository does, since it's the other repository's Travis-CI that stores the access token now, which you should be able to restrict access to better than the main repository's Travis-CI. However, since the building happens in other repository's Travis-CI, it doesn't know when git push events happen in the main repository, so you won't be able to build on every git push to the main repository, instead you would have to use Travis-CI's Cron Jobs to run a build once a day.

Here is a table summarizing the three ways to make releases:

|                                              | Same repo | Different repo | Separate       |
|----------------------------------------------|-----------|----------------|----------------|
| Main repo access token permissions           | Write     | Read           | Read           |
| Different repo access token permissions      | -         | Write          | Write          |
| Access token stored in Travis-CI of          | Main repo | Main repo      | Different repo |
| Artifact production happens on Travis-CI of  | Main repo | Main repo      | Different repo |
| Releases can be made on every main repo push | Yes       | Yes            | No             |

### Publishing to the same repository

1. [Create a new GitHub user](https://github.com/join) that will be used solely for creating releases. For security reasons, we advise that you create a separate user for every repository you want to setup releases for.
2. Under that user, [create a new Personal Access Token](https://github.com/settings/tokens/new) with `repo` access checked if you use `travis-ci.com` or with just `public_repo` access checked if you use `travis-ci.org`.
3. On the Settings page for your repository on Travis-CI, e.g. https://travis-ci.org/nurupo/ci-release-publisher/settings, under Environment Variables, add a new environment variable with the name `GITHUB_ACCESS_TOKEN` and the access token you got off GitHub as the value. Make sure "Display value in build log" is unchecked when adding it. If you already use `GITHUB_ACCESS_TOKEN` for something else, you can name the variable `CIRP_GITHUB_ACCESS_TOKEN` instead.
4. Invite the user as a collaborator to the repository such that the user has Write access to the repository, i.e. can push into it.
5. Accept the invite as the new user.
6. As the new user, log into Travis-CI, which would prompt you to authorize Travis-CI to access your GitHub information -- accept that.
7. Make sure the new user can access Travis-CI page with build details for the repository.

    ---

    It's advised to create a new user per repository because [there were](https://blog.travis-ci.com/2016-07-07-security-advisory-encrypted-variables) multiple [security incidents](https://blog.travis-ci.com/2017-05-08-security-advisory) when GitHub access tokens stored in Travis-CI environment variables were leaked, which essentially equals to the user account the access token belongs to being compromised, as the attacker would be able to push code, publish releases, etc. into all repositories the user has access to. Creating a user per repository helps to limit the possible damage that can be done if the API key does get leaked. Note, however, that [GitHub ToS](https://help.github.com/articles/github-terms-of-service/#3-account-requirements) allows you to have only one "machine account", creating more accounts would technically violate ToS and should be done at your own risk. To minimize the damage even more, set your GitHub repository to disallow force pushes on all branches, require all changes to go through PRs before they get merged and require PRs to be reviewed by other contributors -- that way it's less likely someone would be able to sneak malicious code change in the repository if the access token does get compromised.

    ---

8. In your `.travis.yml`, identify jobs that produce artifacts.

    At the end of the `script` section of all artifact producing jobs add:

    ```yaml
    - .travis/cirp/cleanup1.sh
    - .travis/cirp/store.sh "$TRAVIS_BUILD_DIR/artifacts"
    - .travis/cirp/cleanup2.sh
    ```

    where `$TRAVIS_BUILD_DIR/artifacts` is the path where the artifacts can be found. This will store the artifacts in a temporary store release. We will download them back and delete these temporary store releases in a publishing stage later in the build.

    Now identify artifact producing stages. If a stage contains at least one artifact producing job, we call it an artifact producing stage. It can contain other jobs that don't produce artifacts. You can have as many artifact producing stages as you want, with as many stages that don't produce artifacts before, after and in between them as you want.

    At the end of `script` section of all jobs that are in artifact producing stages but don't actually produce artifacts, add:

    ```yaml
    - .travis/cirp/cleanup1.sh
    - .travis/cirp/cleanup2.sh
    ```

    This will remove the temporary store releases in case of a build failure so that they don't litter your Releases page.

    Find the last artifact producing stage. If you have any stages after it, you can pick any of them to add the publishing job to. If you don't have any stages after it, you can create a publishing stage with the publishing job in it. You can have only one publishing job in the entire build, it must be positioned after all the artifact producing jobs, in separate stage from artifact producing jobs. You should not put the publishing job in the same stage as an artifact producing job. Your publishing job should look like this:

    ```yaml
    if: type != pull_request
    script:
      - export ARTIFACTS_DIR="$(mktemp -d)"
      - .travis/cirp/collect.sh "$ARTIFACTS_DIR"
      - .travis/cirp/cleanup4.sh
      - .travis/cirp/publish.sh "$ARTIFACTS_DIR"
      - .travis/cirp/cleanup5.sh
    ```

    where `$ARTIFACTS_DIR` is the path where artifacts from the temporary store releases will be downloaded.

    Now identify all stages that don't produce artifacts between the first artifact producing stage and the publishing stage, if there are any. Add the following at the end of `script` section of those jobs:

    ```yaml
    - .travis/cirp/cleanup3.sh
    ```

    This will remove the temporary store releases in case of a build failure so that they don't litter your Releases page.

    You should add the following to your `.travis.yml` to avoid Travis-CI building the tags GitHub will be creating due to CI Release Publisher creating non-draft releases:

    ```yaml
    branches:
      except:
        - # Do not run Travis-CI builds on tags CI Release Publisher creates as it
        - # will lead to endless (recursive?) tag creation and Travis-CI running
        - /^ci-.+$/
    ```

    ---

    Here is a sample `.travis.yml` before following these instructions. `...` are omitted parts and `env` is used for commenting on jobs. This is a rather extensive example, with a lot of stages and jobs, which should hopefully cover most of the cases.

    ```yaml
    ...

    matrix:
      include:
        - stage: "Stage 1"
          env: JOB="1" DESC="This job doesn't produce any artifacts"
          script:
            - ...
        - stage: "Stage 2"
          env: JOB="2" DESC="This job doesn't produce any artifacts"
          script:
            - ...
        - stage: "Stage 2"
          env: JOB="3" DESC="This job produces artifacts"
          script:
            - ...
        - stage: "Stage 3"
          env: JOB="4" DESC="This job doesn't produce any artifacts"
          script:
            - ...
        - stage: "Stage 4"
          env: JOB="5" DESC="This job produces artifacts"
          script:
            - ...
        - stage: "Stage 4"
          env: JOB="6" DESC="This job doesn't produce any artifacts"
          script:
            - ...
        - stage: "Stage 5"
          env: JOB="7" DESC="This job doesn't produce any artifacts"
          script:
            - ...
        - stage: "Stage 6"
          env: JOB="8" DESC="This job doesn't produce any artifacts"
          script:
            - ...
        - stage: "Stage 7"
          env: JOB="9" DESC="This job doesn't produce any artifacts"
          script:
            - ...
    ...
    ```

    First, let's identify the artifact producing jobs. These are Job 3 and 5.

    We will add the following to the end of the `script` section of Job 3 and 5:

    ```yaml
    - .travis/cirp/cleanup1.sh
    - .travis/cirp/store.sh "$TRAVIS_BUILD_DIR/artifacts"
    - .travis/cirp/cleanup2.sh
    ```

    Since jobs 3 and 5 are artifact producing jobs, this means that the stages they are in, Stage 2 and Stage 4, are the artifact producing stages.

    We will add the following at the end of `script` section of all jobs in Stage 2 and 4 that are not jobs 3 and 5, that's Job 2 and 6:

    ```yaml
    - .travis/cirp/cleanup1.sh
    - .travis/cirp/cleanup2.sh
    ```

    Since Stage 4 is the last artifact producing stage, we can add the publishing job to any stage after it -- Stage 5, 6 or 7 -- or create a new publishing stage, e.g. Stage 8. For the sake of the example, let's say that we want to add the publishing job to Stage 6.

    We will add the following job to the existing Stage 6:

    ```yaml
    - stage: "Stage 6"
      env: JOB="8.5" DESC="This is a publishing job"
      if: type != pull_request
      script:
        - export ARTIFACTS_DIR="$(mktemp -d)"
        - .travis/cirp/collect.sh "$ARTIFACTS_DIR"
        - .travis/cirp/cleanup4.sh
        - .travis/cirp/publish.sh "$ARTIFACTS_DIR"
        - .travis/cirp/cleanup5.sh
    ```

    With Stage 2 being the first artifact producing stage and Stage 6 being the publishing stage, there are only two stages between them that are not artifact producing stages -- Stage 3 and 5.

    We will add the following to `script` section of all jobs in Stage 3 and 5, that's Job 4 and 7:

    ```yaml
    - .travis/cirp/cleanup3.sh
    ```

    Now just to add the branch exception and we are done:

    ```yaml
    branches:
      except:
        - # Do not run Travis-CI builds on tags CI Release Publisher creates as it
        - # will lead to endless (recursive?) tag creation and Travis-CI running
        - /^ci-.+$/
    ```

    If we follow the instructions, our `.travis.yml` will change to:

    ```yaml
    ...

    matrix:
      include:
        - stage: "Stage 1"
          env: JOB="1" DESC="This job doesn't produce any artifacts"
          script:
            - ...
        - stage: "Stage 2"
          env: JOB="2" DESC="This job doesn't produce any artifacts"
          script:
            - ...
            - .travis/cirp/cleanup1.sh
            - .travis/cirp/cleanup2.sh
        - stage: "Stage 2"
          env: JOB="3" DESC="This job produces artifacts"
          script:
            - ...
            - .travis/cirp/cleanup1.sh
            - .travis/cirp/store.sh "$TRAVIS_BUILD_DIR/artifacts"
            - .travis/cirp/cleanup2.sh
        - stage: "Stage 3"
          env: JOB="4" DESC="This job doesn't produce any artifacts"
          script:
            - ...
            - .travis/cirp/cleanup3.sh
        - stage: "Stage 4"
          env: JOB="5" DESC="This job produces artifacts"
          script:
            - ...
            - .travis/cirp/cleanup1.sh
            - .travis/cirp/store.sh "$TRAVIS_BUILD_DIR/artifacts"
            - .travis/cirp/cleanup2.sh
        - stage: "Stage 4"
          env: JOB="6" DESC="This job doesn't produce any artifacts"
          script:
            - ...
            - .travis/cirp/cleanup1.sh
            - .travis/cirp/cleanup2.sh
        - stage: "Stage 5"
          env: JOB="7" DESC="This job doesn't produce any artifacts"
          script:
            - ...
            - .travis/cirp/cleanup3.sh
        - stage: "Stage 6"
          env: JOB="8" DESC="This job doesn't produce any artifacts"
          script:
            - ...
        - stage: "Stage 6"
          env: JOB="8.5" DESC="This is a publishing job"
          if: type != pull_request
          script:
            - export ARTIFACTS_DIR="$(mktemp -d)"
            - .travis/cirp/collect.sh "$ARTIFACTS_DIR"
            - .travis/cirp/cleanup4.sh
            - .travis/cirp/publish.sh "$ARTIFACTS_DIR"
            - .travis/cirp/cleanup5.sh
        - stage: "Stage 7"
          env: JOB="9" DESC="This job doesn't produce any artifacts"
          script:
            - ...

    branches:
      except:
        - # Do not run Travis-CI builds on tags CI Release Publisher creates as it
        - # will lead to endless (recursive?) tag creation and Travis-CI running
        - /^ci-.+$/
    ...
    ```

    `.travis/cirp/*.sh` are helper scripts that you can find in the `scripts` directory.

9. General dos and don'ts.

    Dos:
    - Do use `.travis/cirp/*.sh` helper scripts, they check for some important preconditions to be met before installing all of CI Release Publisher's dependencies and calling it.
    - Do modify `publish.sh` script to call the `publish` command with the arguments you want.
    - Do run things between the `collect.sh` and `publish.sh` calls. For example calculate hashes of the artifacts and include them as a file in the artifacts directory for `publish.sh` to upload, or modify `publish.sh` to calculate the hashes and pass them as the release body text argument, or generate a changelog and set it as the release body text.
    - Do modify `store.sh` script to call the `store` command with the arguments you want.
    - Do modify `install.sh` for your needs.
    - Do modify `check_precondition.sh` for your needs.
    - Do use Travis-CI's `allow_failures` feature if you want to allow an artifact producing job to fail, the `cleanup*.sh` scripts will make sure that the build artifacts of these jobs are not included in the release.
    - Do set `--tag-prefix` on all of the python script invocations in all `*.sh` scripts if you already use branch names or tag names that start with `ci-`or `_ci-` for something else, as CI Release publisher might delete them.
    - Do set `--tag-prefix-incomplete-releases` on all of the python script invocations in all `*.sh` scripts if you have branches or tags that differ by the starting `_`, e.g. `<name>` and `_<name>`, as CI Release publisher might delete them.

    Don'ts:
    - Don't modify `cleanup*.sh` scripts, especially the arguments passed to `cleanup` commands. They are the exact arguments you want to call `cleanup` commands with, changing them without having a deep understanding of why they are needed will very likely break things.
    - Don't remove `cleanup*.sh` calls from your `travis.yml`. They are rather numerous, but they are there to minimize the littering of the Releases page with draft releases. Also, some other commands, like `store`, depend on the exact `cleanup` command to be called right before them and will misbehave if the cleanup is removed.
    - Don't re-arrange the order in which `*.sh` scripts are called, doing so will break the logic.

### Publishing to a different repository

1. Follow all the steps from [Publishing to the same repository](#publishing-to-the-same-repository), except that you add the access token to main repository's Travis-CI for the step 3 and invite the new user to a different, non-main, repository for the step 4.

2. In addition to the `.travis.yml` modifications done in the step 8, you should set `CIRP_GITHUB_REPO_SLUG` environment variable before calling CI Release Publisher, to tell it that it should publish releases to a different repository. `CIRP_GITHUB_REPO_SLUG` should be set to `<github-user-or-org-name>/<repo-name>`, i.e. the part of repository URL with "https://github.com/" dropped, e.g. for `https://github.com/nurupo/ci-release-publisher` that would be `nurupo/ci-release-publisher`. Since it needs to be set every time you run CI Release Publisher, it's easier [to set it globally](https://docs.travis-ci.com/user/environment-variables/#global-variables) like this:

    ```yaml
    env:
      global:
        - CIRP_GITHUB_REPO_SLUG="nurupo/ci-release-publisher"
    ```

3. Make sure the GitHub repository you want to publish releases to has at least one commit, since GitHub releases are just constructs on top of git tags and you can't have git tags without having any commits.

In contrast to publishing to the same repository, CI Release Publisher doesn't set `target_commitish` to `$TRAVIS_COMMIT` in [the release creating GtHub API call](https://developer.github.com/v3/repos/releases/#create-a-release) when publishing to a different repository, it leaves it empty, which means that [the release will be created with a tag referencing the default branch for the GitHub rpository](https://developer.github.com/v3/repos/releases/#create-a-release). It's done so because if you set `target_commitish` to `$TRAVIS_COMMIT`, which is the commit that was just pushed to the main repository, and such commit doesn't exist in the different repository -- GitHub API would error out since it can't create a tag for a non-existing commit. It's a fair assumption that the different repository won't be up-to-date with whatever was just pushed to the main repository. You can override this behavior by providing `--*target-commitish` arguments to CI Release Publisher's `store` and `publish` commands.

### Doing everything in a different repository

The idea here is to setup a Travis-CI cron build in a different repository to run daily/weekly/monthly which will `git pull` a branch of the main repository, modify `.travis.yml` of the repository we just pulled so that it would use CI Release Publisher to create build artifacts and publish them in the current repository, and `git push` it all into some branch of the different repository. The act of pushing will start another Travis-CI build, which this time will publish releases. We don't want to publish releases in the cron build because if there are several artifact producing jobs, each doing `git pull` on the main repository, it's possible that the main repository will get new commits pushed while our build is running resulting in some jobs pulling an older history and other a newer one, so the resulting build artifacts might be of different commits. By pulling the main repository in the cron build and pushing it into a different repository's branch we guarantee that all jobs will work on the same revision of the main repository.

1. Follow the steps 1-7 in [Publishing to the same repository](#publishing-to-the-same-repository), storing the access token into the different repository's Travis-CI and inviting the new user to the different repository.

2. Follow steps 8 and 9 to create `.travis.build.yml` file, which is what we will replace main repository's `.travis.yml` with.

3. Create a `.travis.yml` with:

    ```yaml
    env:
      - MAIN_REPO_SLUG="nurupo/ci-release-publisher" MAIN_REPO_BRANCH="master" DIFFERENT_REPO_BRANCH="build"

    cache:
      directories:
        - /tmp/cirp

    script:
      - ./update_branch.sh
    ```

    Modify the environment variables appropriately.

    We use [Travis-CI's cache functionality](https://docs.travis-ci.com/user/caching/) to store the hash of the latest commit we have made a release for, so that we don't create a new release next time if nothing has changed in the main repository. Of course there are cases when you want to make a new release even though nothing has changed in the main repository, e.g. when one of the dependencies updates, like OpenSSL, but this is out of scope of this example and you could expand on this caching solution to cover that.

    Note that [Travis-CI's cache expiers in 28 days](https://docs.travis-ci.com/user/caching/#caches-expiration) for open source projects (it's longer for private projects), while it's not specified how much time passes between Travis-CI's monthly cron builds. The exact time at which Travis-CI runs cron builds is documented as implementation-defined, so Travis-CI can change it at any time, but based on some observations, it currently seems to run monthly cron builds at the exact same date and time as the first monthly cron job has ran but with a month incremented, e.g. 2019-02-19 09:00:00 -> 2019-03-19 09:00:00 -> 2019-04-19 09:00:00 -> 2019-05-19 09:00:00. If that's the case, then at least 28 days would pass since the last run, meaning that the cache would always expire by the time the next monthly cron build runs, so you probably won't be benefiting from using the cache in your monthly cron builds.

4. Create a `update_branch.sh` file, marking it as executable, with something like the following (it's likely you will want to customize this):

    ```bash
    #!/usr/bin/env bash

    set -euo pipefail

    # Put away our travis config for now
    cp .travis.${DIFFERENT_REPO_BRANCH}.yml ..

    # Checkout main repository's branch
    git remote rm origin
    git remote add origin https://$GITHUB_ACCESS_TOKEN@github.com/$TRAVIS_REPO_SLUG > /dev/null 2>&1
    git remote add upstream https://github.com/$MAIN_REPO_SLUG > /dev/null 2>&1
    git fetch upstream > /dev/null 2>&1
    git branch -D $DIFFERENT_REPO_BRANCH || true
    git checkout -b $DIFFERENT_REPO_BRANCH upstream/$MAIN_REPO_BRANCH
    git log -1

    # Don't create a new release if the main repository hasn't updated since the previous release
    if [ -f "/tmp/cirp/previous_runs_commit" ]; then
      if [ "$(cat /tmp/cirp/previous_runs_commit)" == "$(git rev-parse HEAD)" ]; then
        echo "The main repository hasn't been updated since the last release. Exiting."
        exit 0
      else
        # Main repo got new commits in it
        git rev-parse HEAD > /tmp/cirp/previous_runs_commit
      fi
    else
      # Caching last commit information as it doesn't exist
      mkdir -p /tmp/cirp
      git rev-parse HEAD > /tmp/cirp/previous_runs_commit
    fi

    # Patch up the main repo's Travis-CI configuration so that it creates releases
    mv ../.travis.${DIFFERENT_REPO_BRANCH}.yml .travis.yml
    # you might want to patch more things here, perhaps add some bash scripts that
    # .travis.${DIFFERENT_REPO_BRANCH}.yml will be calling that are not present in
    # the main repo, apply actual patch files, sed things, etc.

    # Push the changes to our branch
    git config --global user.email "new-users-email@example.com"
    git config --global user.name "new-users-name"
    git commit -am "Modify upstream repo for building"
    git push origin $DIFFERENT_REPO_BRANCH --force > /dev/null 2>&1
    ```

    Change `$GITHUB_ACCESS_TOKEN` to `$CIRP_GITHUB_ACCESS_TOKEN` if you are using the latter, and include the access token into `git remote add upstream` command's URL if the main repository is private, otherwise we wouldn't be able to clone it. Change `new-users-email@example.com` to new user's email address and `new-users-name` to new user's name. Remove output of all commands that might leak the access token with `> /dev/null 2>&1`, and make sure you don't expose `.git/config` anywhere, since that's where all remote URLs with access tokens in them are stored. Travis-CI has [documentation](https://docs.travis-ci.com/user/best-practices-security/#recommendations-on-how-to-avoid-leaking-secrets-to-build-logs) on best practices of preventing access tokens from being leaked to build logs.

    Note that this simple `update_branch.sh` script won't create releases for any tags created in the main repository, but you could expand it to do so.

5. Modify `.travis.yml` and `update_branch.sh` to your needs.
6. Push `.travis.yml`, `update_branch.sh` and `.travis.build.yml` into the different repository.
7. After you push, make sure the build gets created on Travis-CI, that it succeeds, that in turn it creates yet another build which succeeds and creates releases.
8. Go to the Settings page of your repository on Travis-CI, e.g. https://travis-ci.org/nurupo/ci-release-publisher/settings, and under "Cron Jobs" set it to run a cron build of the branch you pushed the files to daily, weekly or monthly.

## Command line arguments

It's often useful to know what options a program provides before installing it, so here are all of the available command line arguments.

Note that CI Release Publisher uses `$TRAVIS_` environment variables to know which branch it's running on, whether a tag was pushed and so on, so you won't see command line arguments on specifying things CI Release Publisher can already get from the `$TRAVIS_` environment variables.

<details>
  <summary>ci-release-publisher --version</summary>

  ```
  0.1.0
  ```
</details>

<details>
  <summary>ci-release-publisher --help</summary>

  ```
  usage: ci-release-publisher [-h] [--version] [--travis-api-url TRAVIS_API_URL]
                              [--github-api-url GITHUB_API_URL]
                              [--tag-prefix TAG_PREFIX]
                              [--tag-prefix-incomplete-releases TAG_PREFIX_TMP]
                              {store,cleanup_store,collect,publish,cleanup_publish}
                              ...

  A script for publishing Travis-CI build artifacts on GitHub Releases

  positional arguments:
    {store,cleanup_store,collect,publish,cleanup_publish}
      store               Store artifacts of the current job in a draft release
                          for the later collection by a job calling the
                          "publish" command.
      cleanup_store       Delete the releases created by the "store" command.
      collect             Collect artifacts from all draft releases created by
                          the "store" command during the current build in a
                          directory.
      publish             Publish releases with artifacts from a directory.
      cleanup_publish     Delete incomplete releases left over by the "publish"
                          command by the current and previous builds.

  optional arguments:
    -h, --help            show this help message and exit
    --version             show program's version number and exit
    --travis-api-url TRAVIS_API_URL
                          Use a custom Travis-CI API URL, e.g. for self-hosted
                          Travis-CI Enterprise instance. Should be an URL to the
                          API endpoint, e.g. "https://travis.example.com/api".
    --github-api-url GITHUB_API_URL
                          Use a custom GitHib API URL, e.g. for self-hosted
                          GitHub Enterprise instance. Should be an URL to the
                          API endpoint, e.g. "https://api.github.com".
    --tag-prefix TAG_PREFIX
                          git tag prefix to use when creating releases.
    --tag-prefix-incomplete-releases TAG_PREFIX_TMP
                          An additional git tag prefix, on top of the existing
                          one, to use for indicating incomplete, in-progress
                          releases.
  ```
</details>

<details>
  <summary>ci-release-publisher store --help</summary>

  ```
  usage: ci-release-publisher store [-h] [--release-name RELEASE_NAME]
                                    [--release-body RELEASE_BODY]
                                    ARTIFACT_DIR

  positional arguments:
    ARTIFACT_DIR          Path to a directory containing artifacts that need to
                          be stored.

  optional arguments:
    -h, --help            show this help message and exit
    --release-name RELEASE_NAME
                          Release name text. If not specified a predefined text
                          is used.
    --release-body RELEASE_BODY
                          Release body text. If not specified a predefined text
                          is used.
  ```
</details>

<details>
  <summary>ci-release-publisher cleanup_store --help</summary>

  ```
  usage: ci-release-publisher cleanup_store [-h] --scope
                                            {current-job,current-build,previous-finished-builds}
                                            [{current-job,current-build,previous-finished-builds} ...]
                                            --release {complete,incomplete}
                                            [{complete,incomplete} ...]
                                            [--on-nonallowed-failure]

  optional arguments:
    -h, --help            show this help message and exit
    --scope {current-job,current-build,previous-finished-builds} [{current-job,current-build,previous-finished-builds} ...]
                          Scope to cleanup.
    --release {complete,incomplete} [{complete,incomplete} ...]
                          Release to cleanup.
    --on-nonallowed-failure
                          Cleanup only if the current build has a job that both
                          has failed and doesn't have allow_failure set on it,
                          i.e. the current build is going to fail once the
                          current stage finishes running.
  ```
</details>

<details>
  <summary>ci-release-publisher collect --help</summary>

  ```
  usage: ci-release-publisher collect [-h] ARTIFACT_DIR

  positional arguments:
    ARTIFACT_DIR  Path to a directory where artifacts should be collected to.

  optional arguments:
    -h, --help    show this help message and exit
  ```
</details>

<details>
  <summary>ci-release-publisher publish --help</summary>

  ```
  usage: ci-release-publisher publish [-h] [--latest-release]
                                      [--latest-release-name LATEST_RELEASE_NAME]
                                      [--latest-release-body LATEST_RELEASE_BODY]
                                      [--latest-release-draft]
                                      [--latest-release-prerelease]
                                      [--latest-release-target-commitish LATEST_RELEASE_TARGET_COMMITISH]
                                      [--numbered-release]
                                      [--numbered-release-keep-count NUMBERED_RELEASE_KEEP_COUNT]
                                      [--numbered-release-keep-time NUMBERED_RELEASE_KEEP_TIME]
                                      [--numbered-release-name NUMBERED_RELEASE_NAME]
                                      [--numbered-release-body NUMBERED_RELEASE_BODY]
                                      [--numbered-release-draft]
                                      [--numbered-release-prerelease]
                                      [--numbered-release-target-commitish NUMBERED_RELEASE_TARGET_COMMITISH]
                                      [--tag-release]
                                      [--tag-release-name TAG_RELEASE_NAME]
                                      [--tag-release-body TAG_RELEASE_BODY]
                                      [--tag-release-draft]
                                      [--tag-release-prerelease]
                                      [--tag-release-target-commitish TAG_RELEASE_TARGET_COMMITISH]
                                      [--tag-release-force-recreate]
                                      ARTIFACT_DIR

  positional arguments:
    ARTIFACT_DIR          Path to a directory containing build artifacts to
                          publish.

  optional arguments:
    -h, --help            show this help message and exit
    --latest-release      Publish latest release. The same "ci-<branch>-latest"
                          tag release will be re-used (re-created) by each
                          build.
    --latest-release-name LATEST_RELEASE_NAME
                          Release name text. If not specified a predefined text
                          is used.
    --latest-release-body LATEST_RELEASE_BODY
                          Release body text. If not specified a predefined text
                          is used.
    --latest-release-draft
                          Publish as a draft.
    --latest-release-prerelease
                          Publish as a prerelease.
    --latest-release-target-commitish LATEST_RELEASE_TARGET_COMMITISH
                          Commit the release should point to. By default it's
                          set to $TRAVIS_COMMIT when publishing to the same repo
                          and not set when publishing to a different repo.
    --numbered-release    Publish a numbered release. A separate
                          "ci-<branch>-<build_number>" release will be made for
                          each build. You must specify at least one of
                          --numbered-release-keep-* arguments specifying the
                          strategy for keeping numbered builds.
    --numbered-release-keep-count NUMBERED_RELEASE_KEEP_COUNT
                          Number of numbered releases to keep. If set to 0, this
                          check is disabled, otherwise if the number of numbered
                          releases exceeds that number, the oldest numbered
                          release will be deleted. Note that due to a race
                          condition of several Travis-CI builds running at the
                          same time, although unlikely, it's possible for the
                          number of kept numbered releases to exceed that number
                          by the number of concurrent Travis-CI builds running.
    --numbered-release-keep-time NUMBERED_RELEASE_KEEP_TIME
                          How long to keep the numbered releases for, in
                          seconds. If set to 0, this check is disabled,
                          otherwise all numbered releases that are older than
                          the specified amount of seconds will be deleted.
    --numbered-release-name NUMBERED_RELEASE_NAME
                          Release name text. If not specified a predefined text
                          is used.
    --numbered-release-body NUMBERED_RELEASE_BODY
                          Release body text. If not specified a predefined text
                          is used.
    --numbered-release-draft
                          Publish as a draft.
    --numbered-release-prerelease
                          Publish as a prerelease.
    --numbered-release-target-commitish NUMBERED_RELEASE_TARGET_COMMITISH
                          Commit the release should point to. By default it's
                          set to $TRAVIS_COMMIT when publishing to the same repo
                          and not set when publishing to a different repo.
    --tag-release         Publish a release for a pushed tag. A separate "<tag>"
                          release will be made whenever a tag is pushed.
    --tag-release-name TAG_RELEASE_NAME
                          Release name text. If not specified a predefined text
                          is used.
    --tag-release-body TAG_RELEASE_BODY
                          Release body text. If not specified a predefined text
                          is used.
    --tag-release-draft   Publish as a draft.
    --tag-release-prerelease
                          Publish as a prerelease.
    --tag-release-target-commitish TAG_RELEASE_TARGET_COMMITISH
                          Commit the release should point to. By default it's
                          set to $TRAVIS_COMMIT when publishing to the same repo
                          and not set when publishing to a different repo.
    --tag-release-force-recreate
                          Force recreation of the release if it already exists.
                          DANGER. You almost never want to enable this option.
                          When enabled, your existing tag release will be
                          deleted, all of its text and artifacts will be forever
                          lost, and a new tag release will be created based on
                          this build. Note that by enabling this, someone might
                          accidentally (or not) restart a tag release build on
                          Travis-CI, causing the release to be recreated. You
                          have been warned.
  ```
</details>

<details>
  <summary>ci-release-publisher cleanup_publish --help</summary>

  ```
  usage: ci-release-publisher cleanup_publish [-h]

  optional arguments:
    -h, --help  show this help message and exit
  ```
</details>

## Troubleshooting

In order to prevent GitHub access token from being leaked, CI Release Publisher catches all exceptions and prints out only the exception type and message, avoiding printing out the stack trace, as the access token is often passed as a function argument and might show up in the stack trace. Although a good security measure, it also means that you don't know where exactly in the code exceptions are coming from. Luckily there are just a few common exceptions that happen when using CI Release Publisher incorrectly, most of which have to do with using the wrong API endpoint for either GitHub or Travis-CI, incorrect GitHub access token or an access token with insufficient permissions set. This section tries to document those exceptions based on just exception type and message.

### `JSONDecodeError`

If you are getting:

```
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

it's likely that Travis-CI can't authenticate CI Release Publisher using the GitHub access token provided. Make sure you have set the right scope on the access token, e.g. `repo` for Travis-CI on `.com` and `public_repo` for Travis-CI on `.org`, and that you have logged into Travis-CI web interface at least once as the GitHub user whose access token you are using, authorizing Travis-CI to access that user's GitHub account, so that Travis-CI would create an account for the GitHub user.

If you have access to `$GITHUB_ACCESS_TOKEN` locally on your machine, you can test Travis-CI authentication with GitHub access token using this cURL command:

```bash
curl -v -X POST \
-H "Accept: application/vnd.travis-ci.2.1+json" \
-d 'github_token=$GITHUB_ACCESS_TOKEN' \
'https://api.travis-ci.org/auth/github'
```

You want to see a 2xx HTTP code and a Travis-CI access token as a payload in the reply. Again, run this locally, don't run it on Travis-CI as it might reveal `$GITHUB_ACCESS_TOKEN` and it will reveal your Travis-CI access token on success.

### `BadCredentialsException`

If you are getting:

```
BadCredentialsException: 401 {'message': 'Bad credentials', 'documentation_url': 'https://developer.github.com/v3'}
```

then it means that the GitHub access token you provided doesn't have enough permissions to create releases in the target GitHub repository. Make sure you have invited the new user to the repository, the new user has accepted the invitation and they have been granted the full write access to it.

## License

MIT
