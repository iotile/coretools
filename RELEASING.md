This is a formalization of our release process that attempts to clarify the 
criteria for release. We still use versioning from [SemVer](http://semver.org).


### Release Noise

In the past, we have released generally on a whim by cutting a minor version when a fix
gets applied for a particular bug or problem that an individual wants to use. However,
in many cases, the external audience does not need or want this fix, and pushing it immediately
increases the risk that someone else's workflow breaks. When this happens with high frequency,
it can be frustrating to work with.

To reduce release noise, we are establishing additional release rules

## Release Rules

##### Patch change rules

Patches should generally not require their own release for active components. In general,
patches should be part of HEAD for **two weeks** before creating an official release, unless
the change is immediately required by an external user to unblock their workflow. Changes like
this should be approved through our normal release process.

##### Minor change rules

In general, we don't want to release minor version bumps of components more frequently than
every **two weeks**. We do not wish to impose a strict release schedule at this point, however,
so this is just a rough guideline. The two week timer begins when the first new code gets committed in to a 
component. This is to ensure that developers have more time and chance to get exposed to the changes
before they are exposed to external users.

##### Major change rules

Major changes typically represent major API changes to the code, and must not be released
directly to master without additional testing. Major changes should be part of a release 
candidate for at least **one week** before they are promoted to a full release, or longer
depending on the complexity. They should have documented testing done (in the PR or elsewhere)
and several people should be involved in vetting the new code internally.