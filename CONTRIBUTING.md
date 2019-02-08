# Contributing

When contributing to this repository, please first discuss the change you wish to make via issue,
email, or any other method with the owners of this repository before making a change. 

Please note we have a code of conduct, please follow it in all your interactions with the project.

## Coding Guidelines

- We generally follow PEP8 for style, and you can see the `.pylintrc` file to check your code as you develop.
For more detailed descriptions of our guidelines, use [Google's](https://github.com/google/styleguide/blob/gh-pages/pyguide.md) style.

- Since this is a mature codebase, not all of the current code conforms. It will be ported over and once all code 
in a package follows the styleguide, CI checking using pylint will be turned on to enforce it going forward.

- You should strive to include test coverage for new features you author. If you happen to be revising old code that 
doesn't have tests, consider adding some! 

- We must maintain compatibility with Python2.7 and Python3.6 on MacOS, Linux and Windows. 

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

1. If you are releasing a feature that will create a new version of a package, update the RELEASE.md 
   and version.py of each component you are modifying with the details of your changes. If you
   are not changing the version, you should still add your changes to a HEAD section in README.md
   regardless. The versioning scheme we use is [SemVer](http://semver.org/).
2. You must clean up your commits in to logical changes before merging. If you are changing multiple
   packages, you should consider using multiple commits. Good practice suggests that smaller, more contained
   feature PRs are easier to review and less prone to regressions.
3. In order to accomplish the above, you can either use git's squash and merge feature, or modify the history
   yourself using something like `git rebase -i` to clean up your history in to modules before rebase and merge.
   We do not permit pure merges (the option that creates Merge commits) at this time.
4. You are required to get at least one maintainer to sign off before you can merge. If nobody has reviewed your
   commit within a day or two, please try to get in touch by tagging or messaging them.
   
In general, it's a good idea to look through some of the most recent closed PRs to get a real sense of 
how we conduct them.

## Code of Conduct

### Our Pledge

In the interest of fostering an open and welcoming environment, we as
contributors and maintainers pledge to making participation in our project and
our community a harassment-free experience for everyone, regardless of age, body
size, disability, ethnicity, gender identity and expression, level of experience,
nationality, personal appearance, race, religion, or sexual identity and
orientation.

### Our Standards

Examples of behavior that contributes to creating a positive environment
include:

* Using welcoming and inclusive language
* Being respectful of differing viewpoints and experiences
* Gracefully accepting constructive criticism
* Focusing on what is best for the community
* Showing empathy towards other community members

Examples of unacceptable behavior by participants include:

* The use of sexualized language or imagery and unwelcome sexual attention or
advances
* Trolling, insulting/derogatory comments, and personal or political attacks
* Public or private harassment
* Publishing others' private information, such as a physical or electronic
  address, without explicit permission
* Other conduct which could reasonably be considered inappropriate in a
  professional setting

### Our Responsibilities

Project maintainers are responsible for clarifying the standards of acceptable
behavior and are expected to take appropriate and fair corrective action in
response to any instances of unacceptable behavior.

Project maintainers have the right and responsibility to remove, edit, or
reject comments, commits, code, wiki edits, issues, and other contributions
that are not aligned to this Code of Conduct, or to ban temporarily or
permanently any contributor for other behaviors that they deem inappropriate,
threatening, offensive, or harmful.

### Scope

This Code of Conduct applies both within project spaces and in public spaces
when an individual is representing the project or its community. Examples of
representing a project or community include using an official project e-mail
address, posting via an official social media account, or acting as an appointed
representative at an online or offline event. Representation of a project may be
further defined and clarified by project maintainers.

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported by contacting the project team at [contact@archsys.io]. All
complaints will be reviewed and investigated and will result in a response that
is deemed necessary and appropriate to the circumstances. The project team is
obligated to maintain confidentiality with regard to the reporter of an incident.
Further details of specific enforcement policies may be posted separately.

Project maintainers who do not follow or enforce the Code of Conduct in good
faith may face temporary or permanent repercussions as determined by other
members of the project's leadership.

### Attribution

This Code of Conduct is adapted from the [Contributor Covenant][homepage], version 1.4,
available at [http://contributor-covenant.org/version/1/4][version]

[homepage]: http://contributor-covenant.org
[version]: http://contributor-covenant.org/version/1/4/