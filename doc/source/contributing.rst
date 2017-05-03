Contributing
============

Contributions are welcome and encouraged to help us improve CoreTools or add
new features that you need.  Contributions should be made in the form of 
Pull Requests and follow these guidelines:

1. Code should conform to the CoreTools styleguide, as described below.
2. Code should have unit test coverage that runs using tox.  Please see
   any of the CoreTools projects for our current tox setup.
3. Code should work on MacOS, Linux and Windows.  Currently we run all
   of our regression tests on Linux and Windows using TravisCI and
   AppVeyor.  
4. Documentation for public objects is required and should conform to 
   the CoreTools styleguide.

Style Guide
-----------

All new contributions to CoreTools must follow the below style guide to
be accepted.  Since this is a mature codebase, not all of the current code 
conforms.  It will be ported over and once all code in a package follows
the styleguide, CI checking using `pylint` will be turned on to enforce it
going forward.

Docstring Style
###############

Docstrings should be written in Google Docstring Format.

Logging vs Printing
###################

All modules should use Python's `logging` module for reporting information, 
not print statements.  Loggers should be created with the name of the module
as their name::
	
	import logging

	logger = logging.getLogger(__name__)

