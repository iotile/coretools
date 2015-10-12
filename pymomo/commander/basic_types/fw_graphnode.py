from pyparsing import Word, Regex, nums, hexnums, Literal, Optional, Group, oneOf, QuotedString
import sys
import os.path
from fw_stream import SensorStream 
from pymomo.exceptions import *

number = Regex('((0x[a-fA-F0-9]+)|[0-9]+)').setParseAction(lambda s,l,t: [int(t[0], 0)])
combiner = (Literal('&&') | Literal('||')).setParseAction(lambda s,l,t: [t[0] == '||']) # True when disjunction
symbol = oneOf("copyA averageA").setParseAction(lambda s,l,t: [processor_list[t[0]]])

stream_type = Literal('input') | Literal('output') | Literal('buffered node') | Literal("unbuffered node") | Literal("constant") | Literal("counter node")
stream = stream_type + number

trigger_type = (Literal('value') | Literal('count')).setParseAction(lambda s,l,t: [t[0] == 'value']) # True when trigger is based on value data
trigger_op = oneOf('> < >= <= =').setParseAction(lambda s,l,t: [trigger_ops[t[0]]])

trigger = Literal('always') | (Literal('when').suppress() + trigger_type('type') + trigger_op + number)

inputstring = stream + trigger

inputdesc2 = Literal('(').suppress() + inputstring('inputA') + combiner('combiner') + inputstring('inputB') + Literal(')').suppress()
inputdesc1 = Literal('(').suppress() + inputstring('inputA') + Literal(')').suppress()

inputdesc = inputdesc1('input1') | inputdesc2('input2')
graph_node = inputdesc + Literal('=>').suppress() + stream('node') + Literal('using').suppress() + symbol('processor')

# Example
# (buffered node 0x100 when value >= 1 || buffered node 0x101 when count >= 5) => buffered node 0x102 using copyA

trigger_ops = {'>': 0, '<': 1, '>=': 2, '<=': 3, '=': 4, 'always': 5}
processor_list = {'copyA': 0, 'averageA': 1, 'copyAllA': 2}

class SensorGraphNode:
	def __init__(self, desc):
		if not isinstance(desc, basestring):
			raise ValidationError("attempting to create a SensorGraphNode without using a string description", description=desc)

		data = graph_node.parseString(desc)

		self.trigger_combiner = 0
		if 'combiner' in data:
			self.trigger_combiner = int(data['combiner'])

		self.inputA = SensorStream(0xFFFF)
		self.triggerA = self._process_trigger({})
		self.inputB = SensorStream(0xFFFF)
		self.triggerB = self._process_trigger({})

		if 'inputA' in data:
			self.inputA = SensorStream(" ".join(map(str, data['inputA'][:2])))
			self.triggerA = self._process_trigger(data['inputA'])

		if "inputB" in data:
			self.inputB = SensorStream(" ".join(map(str, data['inputB'][:2])))
			self.triggerB = self._process_trigger(data['inputB'])

		self.stream = SensorStream(" ".join(map(str, data['node'][:2])))
		self.processor = data['processor']

	def _process_trigger(self, inputdesc):
		"""
		Create an 8-bit trigger op and extract the trigger data
		"""

		if "type" not in inputdesc:
			return (trigger_ops['always'] << 1, 0)

		useValue = inputdesc['type']

		if useValue:
			return (inputdesc[3] << 1, inputdesc[4])
		
		return (1 | (inputdesc[3] << 1), inputdesc[4])

	def __str__(self):
		out = "SensorGraphNode\n"
		out += "  inputA: %d\n" % self.inputA.id
		out += "  inputB: %d\n" % self.inputB.id
		out += "  stream: %d\n" % self.stream.id
		out += "  processor: %d\n" % self.processor

		return out

def convert(arg):
	if isinstance(arg, SensorGraphNode):
		return arg

	return SensorGraphNode(arg)

def default_formatter(arg, **kwargs):
	return str(arg)