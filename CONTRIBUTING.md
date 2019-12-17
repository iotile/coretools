# Contributing

When contributing to this repository, please first discuss the change you wish to make via issue,
email, or any other method with the owners of this repository before submitting a PR. If the

Please note we have a code of conduct, please follow it in all your interactions with the project.

## Coding Guidelines

- We generally follow PEP8 for style, and you can see the `.pylintrc` file to check your code as you develop.
For more detailed descriptions of our guidelines, use [Google's](https://github.com/google/styleguide/blob/gh-pages/pyguide.md) style.

- Since this is a mature codebase, not all of the current code conforms. It will be ported over and once all code
in a package follows the styleguide, CI checking using pylint will be turned on to enforce it going forward.

- You should strive to include test coverage for new features you author. If you happen to be revising old code that
doesn't have tests, consider adding some!

- We must maintain compatibility with Python3.5 on MacOS, Linux and Windows. We also test against 3.6 and 3.7, and should strive
to support them as well (there should be no compatibility issues, if possible)

- Documentation for all public objects must be included in new features. Please use the [guideline](https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)

- All modules should use Python’s logging module for reporting information, not print statements.
Loggers should be created with the name of the module as their name:
```
import logging

logger = logging.getLogger(__name__)
```

## Development recommendation

We use the [feature branch](https://docs.gitlab.com/ee/workflow/workflow.html) model with a rebase strategy.
Using this for development will make it easier for you to merge pull requests.

## Generic Pull Request Process

### TL;DR VERSION

1. Pass tests and validate linting as you develop
2. Write new tests for new functions. Improve old tests!
3. Keep your PR small. Separate it by issue if you need to.
4. Update RELEASE.md notes
5. Be as descriptive as possible in the PR description.
6. Use git tools to manage review flow (resolve comments, re-request)
7. Clean up commits and merge

#### Before submitting your code for review

1. Make sure the tests are passing in your local environment. Your project's dev guide should say how.
2. Make sure that your modifications comply with any style (linting). If you don't have an IDE that's doing
this for you as you code, check your developer guide for assistance.
3. If you're writing new features, you'll probably be asked to write tests for them. Do that before submitting the PR
or it may be rejected/closed until they are written.
4. Even if your PR is small, try to add as much context about your code available as possible. This
is often easiest in the description of the PR. You'll want to include things like:
  - A link to the issue that this PR is resolved
  - Any key design decisions you made in implementation (or a choice that you made)
  - Particular areas where someone should focus their review on (critical algorithms, new complex classes)
5. If you're working on a Python package, make sure you update the RELEASE.md by adding a summary of
   changes to the ##HEAD section (add one if there isn't in the same form as releases are). If you are a
   maintainer, you can promote the HEAD changes to a new version release, and also amend the `version.py` for
   your updated component. Please see [RELEASING.md](RELEASING.md)
6. Re-read your PR with the mindset of your reviewer. You may identify areas for clarification or more context.

#### Once you submit your PR

1. You are required to get at least one maintainer to sign off before you can merge. If nobody has reviewed your
   commit within a day or two, please try to get in touch by tagging or messaging them.
2. Respond to feedback.
  - If you have to make changes, and the reviewer approved it, make the changes, and move on to the next step.
  - If changes are requested explicitly, address them all, resolve the comments, and re-request review
  - When re-requesting, it may be helpful to comment that the review is ready for a final pass.
  - There is a good slide illustration of this [here](https://docs.google.com/presentation/d/1eDB-p76PErEhZI5YJaSJX4Qu3Czct6I7X97IG6SxfWA/edit#slide=id.g64d54012bb_0_74)


#### When you're preparing to merge:

1. You must clean up your commits in to logical changes before merging. If you are changing multiple
   packages, you should consider using multiple commits. Good practice suggests that smaller, more contained
   feature PRs are easier to review and less prone to regressions. In general, it's good if your PR can be squashed
   to a single commit, but we do realize that is not always the best way to track history for some changes.
   - In order to accomplish the above, you can either use git's squash and merge feature (to get a single commit), or modify the history yourself using something like `git rebase -i` to clean up your history in to modules (and force pushing to your feature branch or fork branch) before rebase and merge. We do not allow merge commits at this time in order to keep a more linear commit history for easier rollbacks.


In general, it's a good idea to look through some of the most recent closed PRs to get a real sense of
how we conduct them.
