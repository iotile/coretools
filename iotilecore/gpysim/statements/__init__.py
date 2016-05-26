# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import loghex
import logcaller
import logassert
import logfinished
import logcheckpoint

#Map control bytes to statement handlers
statements = {
		0: logfinished.LogFinished,
		1: loghex.LogHex,
		#2: LogString,
		3: logcaller.LogCaller,
		4: logassert.LogAssert,
		5: logcheckpoint.LogCheckpoint
}