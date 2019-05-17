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

## Pull Request Process

1. Make sure you update the RELEASE.md by adding a summary of changes to the ##HEAD section 
   (add one if there isn't in the same form as releases are). If you are a maintainer, you can
   promote the HEAD changes to a new version release, and also amend the `version.py` for 
   your updated component. Please see [RELEASING.md](RELEASING.md)
2. You must clean up your commits in to logical changes before merging. If you are changing multiple
   packages, you should consider using multiple commits. Good practice suggests that smaller, more contained
   feature PRs are easier to review and less prone to regressions. In general, it's good if your PR can be squashed
   to a single commit, but we do realize that is not always the best way to track history for some changes.
3. In order to accomplish the above, you can either use git's squash and merge feature, or modify the history
   yourself using something like `git rebase -i` to clean up your history in to modules (and force pushing to your feature
   branch or fork branch) before rebase and merge. We do not allow merge commits at this time in order to keep 
   a more linear commit history for easier rollbacks.
4. You are required to get at least one maintainer to sign off before you can merge. If nobody has reviewed your
   commit within a day or two, please try to get in touch by tagging or messaging them.
   
In general, it's a good idea to look through some of the most recent closed PRs to get a real sense of 
how we conduct them.
