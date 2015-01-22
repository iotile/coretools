#!/usr/bin/env python
#pcbtool
#A program for creating BOMs, gerbers and assembly drawings from annotated EAGLE circuit board diagrams.

import sys
import os.path
import os
import shutil

import cmdln
from colorama import init, Fore, Style
from pymomo.utilities.paths import MomoPaths
from pymomo.pybom import board,pricing
from pymomo import pyeagle
from pymomo.utilities.template import RecursiveTemplate
import math 
import itertools

init()

class PCBTool(cmdln.Cmdln):
	name = 'pcbtool'
	def __init__(self):
		self.paths = MomoPaths()
		self.get_identifiers()

		cmdln.Cmdln.__init__(self)

	@cmdln.option('-o', '--output', action='store', help='Output directory to hold created files.')
	@cmdln.option('-p', '--paste', action='store_true', default=False, help='Store the solder paste layer (default: no).')
	def do_fab(self, subcmd, opts, id):
		"""${cmd_name}: Generate fabrication and assembly files for this board.

		Create all of the files required for assembly and fabrication based on this board file.  Board file must be a 2-layer board with metadata tagging as described in the MoMo documentation.
		
		${cmd_usage}
        ${cmd_option_list}
		"""

		if os.path.exists(opts.output) and not os.path.isdir(opts.output):
			self.error("Invalid output location, seems to be a file: %s" % opts.output)
		elif not os.path.exists(opts.output):
			path = os.path.abspath(opts.output)
			os.makedirs(path)

		brd = self.find_identifier(id)
		pyeagle.build_production(brd, opts.output, opts.paste)

	def do_list(self, subcmd, opts):
		"""${cmd_name}: List all known PCB board ids.
		
		${cmd_usage}
        ${cmd_option_list}
		"""
		brds = self.paths.select(self.paths.pcb, filter=lambda x, y, z: z == '' or z == '.brd', include_dirs=True)

		print "Listing all known board ids under <momo_root>/pcb directory"
		print "You may specify any of these ids to select the .brd file shown"
		print "\nBoards:"
		for id, path in sorted(self.ids.iteritems(), key=lambda x:x[0]):
			print Fore.BLUE + "%s:" % id + Style.RESET_ALL + " '%s'" % os.path.relpath(path, start=self.paths.pcb)

		print ""

	@cmdln.option('-v', '--variant', action='store', default='MAIN', help="Assembly variant to process.")
	@cmdln.option('-o', '--output', action='store', help='Output file path, defaults to stdout')
	@cmdln.option('--prices', action='store_true', default=False, help='Include prices in BOM')
	@cmdln.option('-n', '--units', action='store', default=1, type=int, help="Number of units to quote")
	@cmdln.option('-d', '--dist', action='append', default=None, help="Only use the given distributors (e.g. Digi-Key)")
	@cmdln.option('--no-dist', action='append', dest='nodist', default=[], help="Exclude the listed distributors.")
	@cmdln.option('-p', '--packaging', action='append', default=[], help="Only allow the specified packaging (e.g. cut tape).")
	@cmdln.option('--no-package', dest='nopackage', action='append', help="Disallow the specified packaging type (e.g. Custom Reel)")
	@cmdln.option('--no-stock', dest='nostock', action='store_false', default=True, help="Allow out of stock offers.")
	@cmdln.option('-f', '--format', action='store', choices=['csv', 'pdf'], default='csv')
	def do_bom(self, subcmd, opts, id):
		"""${cmd_name}: Create a BOM for the specified assembly variant.

		${cmd_usage}
        ${cmd_option_list}
		"""

		reqs = self.build_pricemodel(opts)
		brd = self.get_board(id)

		if opts.format == 'csv':
			out,close = self.build_outstream(opts)
			brd.export_bom(opts.variant, out, include_costs=opts.prices, cost_quantity=opts.units, requirements=reqs)
			if close:
				out.close()
		elif opts.format == 'pdf' or opts.format == 'html':
			data = brd.variant_data(opts.variant, include_costs=opts.prices, cost_quantity=opts.units, requirements=reqs)
			templ = RecursiveTemplate('bom_template.html')
			templ.add(data)
			formatted = templ.format_temp()

			shutil.move(formatted, opts.output)

	@cmdln.option('-v', '--variant', action='append', default=None, help="Print detailed information about the listed assembly variants.")
	def do_info(self, subcmd, opts, id):
		"""${cmd_name}: Print information about the board file indicated.

		If one or more variant is indicated, print detailed information about those
		assembly variants including the number of line items, etc. 
		all may be passed to --variant to indicate that all assembly variants should
		be printed in detail.

		${cmd_usage}
        ${cmd_option_list}
		"""

		brd = self.get_board(id)

		print "Board Name: " + brd.partname
		print "Dimensions: %sx%s inches" % (brd.height, brd.width)
		print "Number of Assembly Variants: %d" % len(brd.variants)
		print "Assembly Variant Names:", brd.variants.keys()

		if len(brd.unknown) == 0:
			print Fore.GREEN + "All parts matched with part numbers" + Style.RESET_ALL
		else:
			print Fore.RED + "Unmatched parts exist:" + Style.RESET_ALL, brd.unknown

		if opts.variant is None:
			return

		if opts.variant[0] == 'all':
			opts.variant = brd.variants.keys()

		print "\n---Assembly Variant Details---\n"

		for var in opts.variant:
			if var not in brd.variants:
				print Fore.RED + "Variant %s does not exist" + Style.RESET_ALL

			lines = len (brd.variants[var])
			items = sum([len(x) for x in brd.variants[var]])

			print "Variant Name: %s" % var
			print "Distinct BOM Lines: %d" % lines
			print "Total Part Count: %d" % items
			print "Through-Hole Parts: %d" % sum([len(x) for x in brd.variants[var] if x[0].package_info()['pins']>0])
			print "Total Through-Hole Pins: %d" % sum(map(lambda x: x[0].package_info()['pins']*len(x), brd.variants[var])) 
			print "SMD Parts: %d" % sum([len(x) for x in brd.variants[var] if x[0].package_info()['pads']>0])
			print "Total SMD Pads: %d" % sum(map(lambda x: x[0].package_info()['pads']*len(x), brd.variants[var]))
			print ""

	@cmdln.option('-e', '--excess', action='store', type=float, default=0.0, help="Excess percentage to purchase of each component, in %. (rounded up)")
	@cmdln.option('-o', '--output', action='store', help='Output directory to hold created files.')
	def do_order(self, subcmd, opts, *boards):
		"""${cmd_name}: Create an order list that can be pasted into a distributor website for ordering.  Board variants added to the
		order should be specified by giving 3 items:
		<board id> <variant> <number>

		All boards will have the same excess applied.

		${cmd_usage}
        ${cmd_option_list}
		"""

		excess = opts.excess/100.0 + 1

		if len(boards) % 3 != 0:
			self.error("You must specify 3 items per board <id> <variant> <number of units>")

		parts = []

		for i in xrange(0, len(boards), 3):
			id = boards[i]
			var = boards[i+1]
			num = int(boards[i+2])
			brd = self.get_board(id)

			quant = int(math.ceil(num*excess))

			print "Processing %s (%s): %d units with %.0f%% excess" % (id, var, num, opts.excess)
			parts.extend(brd.export_list(var)*quant)

		out,close = self.build_outstream(opts)

		distinct = [(k, len(list(g))) for k,g in itertools.groupby(sorted(parts))]

		for k,g in distinct:
			print "%d, %s" % (g,k) 

		if close:
			out.close()

	@cmdln.option('-v', '--variant', action='store', default='MAIN', help="Assembly variant to quote.")
	@cmdln.option('-n', '--units', action='store', default=1, type=int, help="Number of units to quote")
	@cmdln.option('-e', '--excess', action='store', type=float, default=0.0, help="Excess percentage to purchase of each component, in %. (rounded up)")
	@cmdln.option('-l', '--lines', action='store_true', default=False, help="Show cost of each BOM line")
	@cmdln.option('-d', '--dist', action='append', default=None, help="Only use the given distributors (e.g. Digi-Key)")
	@cmdln.option('--no-dist', action='append', dest='nodist', default=[], help="Exclude the listed distributors.")
	@cmdln.option('-p', '--packaging', action='append', default=[], help="Only allow the specified packaging (e.g. cut tape).")
	@cmdln.option('--no-package', dest='nopackage', action='append', help="Disallow the specified packaging type (e.g. Custom Reel)")
	@cmdln.option('--no-stock', dest='nostock', action='store_false', default=True, help="Allow out of stock offers.")
	def do_quote(self, subcmd, opts, id):
		"""${cmd_name}: Quote a BOM price for this board at the given volume.

		The price is looked up using the Octopart API.  For this to work all parts must be tagged in the EAGLE brd file as described in the MoMo documentation and you must have a valid octopart API key specified in either a config file or the environment

		${cmd_usage}
        ${cmd_option_list}
		"""
		brd = self.get_board(id)

		if opts.variant not in brd.variants:
			self.error("Invalid variant passed (%s), options are: %s" % (opts.variant, str(brd.variants.keys())))

		excess = opts.excess/100.0 + 1
		units = opts.units
		multiplier = units*excess

		model = self.build_pricemodel(opts)

		prices, unmatched = brd.price_variant(opts.variant, multiplier, model)

		for line in unmatched:
			print Fore.RED + "\nCould not find:", map(lambda x: x.name, line), Style.RESET_ALL + '\n'

		print "Price for %d Units with %.0f%% excess" % (units, opts.excess)
		total_price = 0.0

		for i, line in enumerate(prices):
			parts, offer = line
			price = float(offer[0])*multiplier
			if opts.lines:
				desc = "from %s" % offer[1]
				if offer[2] is not None:
					desc += " in %s" % (offer[2])
				
				print "Line %d: $%.2f (%d @ $%.2f) %s" % (i+1, price, len(parts), float(offer[0]), desc), map(lambda x: x.name, parts)
			
			total_price += price

		print "Total price: $%.2f" % total_price
		print "Unit price: $%.2f" % (total_price/units)

	def build_pricemodel(self, opts):
		"""
		Given the arguments passed in opts build a PricingRequirements object that meets those requirements
		"""

		valid_sellers = []
		invalid_sellers = []
		valid_packages = []
		invalid_packages = []
		in_stock = True

		if hasattr(opts, 'dist'):
			valid_sellers = opts.dist

		if hasattr(opts, 'nodist'):
			invalid_sellers = opts.nodist

		if hasattr(opts, 'packaging'):
			valid_packages = opts.packaging

		if hasattr(opts, 'nopackage'):
			invalid_packages = opts.nopackage

		if hasattr(opts, 'nostock'):
			in_stock = opts.nostock

		return pricing.OfferRequirements(	valid_sellers=valid_sellers, invalid_sellers=invalid_sellers,
											valid_packages=valid_packages, invalid_packages=invalid_packages,
											in_stock=in_stock)


	def build_outstream(self, opts):
		"""
		If -o was passed, open that file for writing, otherwise return stdout.  Return a bool indicating if the 
		caller should close the stream when finished.
		"""

		if opts.output is None:
			return (sys.stdout, False)

		try:
			stream = open(opts.output, "w")
		except IOError:
			print "Could not open output file %s for writing." % opts.output
			sys.exit(1)

		return (stream, True)

	def get_identifiers(self):
		ids = self.paths.select(self.paths.pcb, filter=lambda x, y, z: z == '.brd')
		
		#Get all of the parent directory names. If they only correspond to a single .brd file,
		#they can also be used as identifiers
		parent_dirs = map(lambda x: (os.path.basename(os.path.dirname(x)), x), ids)
		seen_dirs = set()
		ambig_dirs = set()

		for d in parent_dirs:			
			if d in seen_dirs:
				ambig_dirs.add(d[0])
			else:
				seen_dirs.add(d)

		valid_dirs = seen_dirs.difference(ambig_dirs)
		brd_ids = map(lambda x: (os.path.basename(x), x), ids)

		ids = valid_dirs | set(brd_ids)

		self.ids = {x[0]: x[1] for x in ids}
		self.ambiguous_ids = ambig_dirs

	def error(self, text):
		print Fore.RED + "Error Occurred" + Style.RESET_ALL
		print text
		sys.exit(1)

	def param_error(self, type, param, fix):
		"""
		Print an error message and then quit.  Print type: param.\nfix
		"""

		print Fore.RED + "%s: " % type + Style.RESET_ALL + "%s\n" % param + fix
		sys.exit(1)

	def find_identifier(self, id):
		"""
		Given a string that may correspond to either a .brd file name or a folder, find if there is an
		unambiguous way to return the correct .brd file corresponding to that id.
		"""

		#Check if id is a path that points to valid file
		if os.path.isfile(id):
			return id
		elif os.path.isfile(os.path.join(self.paths.pcb, id)):
			return os.path.join(self.paths.pcb, id)

		if id in self.ambiguous_ids:
			self.param_error("Ambiguous Board Name Passed", id, "Try specifying the .brd file name directly or use pcbtool list to see valid identifiers.")

		if id not in self.ids:
			self.param_error("Unknown Board Name Passed", id, "Specify either the .brd file name or its parent directory if not ambiguous. You can also specify either an (absolute or relative from cwd) path to a .brd file or a relative path from <momo_root>/pcb")

		return self.ids[id]

	def get_board(self, id):
		"""
		Given a board identifier, get the pybom Board object corresponding to it or quit with an error.
		"""

		brdfile = self.find_identifier(id)
		
		try:
			brd = board.Board.FromEagle(brdfile)
		except ValueError as e:
			self.error(str(e))

		return brd

def main():
	pcbtool = PCBTool()
	return pcbtool.main()