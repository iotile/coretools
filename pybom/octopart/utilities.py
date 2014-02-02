#utilities.py

def assert_class(resp, classname):
	if '__class__' not in resp or resp['__class__'] != classname:
			raise ValueError('Creating class from invalid response dictionary')