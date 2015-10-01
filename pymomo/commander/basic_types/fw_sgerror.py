code_map = {
	0: "No Error",
	1: "Invalid Node Index",
	2: "Unitialized Graph Node",
	3: "Node Already Initialized",
	4: "Invalid Input Index",
	5: "No Processing Function Defined",
	6: "Node Did Not Produce Updated Output",
	7: "Graph is Currently Offline",
	8: "Graph Task is Already Pending",
	9: "Reading Ignored By Current Graph",
	10: "Invalid Processing Function",
	11: "No Available Outputs",
	12: "Stream Not In Use",
	13: "No Space For New Node",
	14: "Invalid Stream Name for Node",
	15: "Stream Already in Use",
	16: "Node Not Triggered"
}

def convert(arg, **kargs):
	return int(arg)

def default_formatter(arg):
	msg = code_map.get(arg, "Unknown Error Code")
	
	if arg == 0:
		return "No Error"
	
	return "SensorGraph Error %d: %s" % (arg, msg)