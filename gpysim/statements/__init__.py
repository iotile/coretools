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