#TODO:
# - add compare_descriptions function that compares the descriptions
#	currently associated with each bom line with those returned from
#	an online database side by side so that you can make sure that 
#	you're matching the right part.
# - Make updating metadata and attributes reflected realtime in board
#	without reloading the board.

from pymomo.utilities.typedargs import *
from pymomo.exceptions import *
from eagle.board import EagleBoard
from pricing import OfferRequirements
import match_engines
from bom_matcher import BOMMatcher
from decimal import Decimal
from production import ProductionFileGenerator
import itertools

#List of all of the types of board file we know how to deal with
board_types = {}
board_types['eagle'] = EagleBoard

@context()
class CircuitBoard:
	"""
	A CircuitBoard that can be used to create a BOM or produce gerbers

	The price of the BOM can be looked up using the Octopart API and 
	complex rules can be specifed to decide who to buy the parts from.
	A CircuitBoard can be created from an annotated pcb CAD file from any
	supported CAD program.  Currently we support EAGLE only but more will
	be added in the future.
	"""

	DefaultEngine = match_engines.OctopartMatcher

	@param("file", "path", "readable", desc="PCB board file to load")
	@param("type", "string", ("list", "eagle"), desc="type of file [eagle is only currently supported option]")
	def __init__(self, file, type='eagle'):
		self.board = board_types[type](file)
		self.clear_pricemodel()

		self._match_engine = CircuitBoard.DefaultEngine

		self.errors = []
		self.warnings = []

		#Process board into variants so that each variant is a list of unique parts
		self.variants = {name: self._process_variant(parts) for name,parts in self.board.data['variants'].iteritems()}

		#Copy all of the attributes from the board into this object, logging errors for any missing data
		self._set_attribute('company', self.board.data)
		self._set_attribute('part', self.board.data)
		self._set_attribute('width', self.board.data)
		self._set_attribute('height', self.board.data)
		self._set_attribute('units', self.board.data)
		self._set_attribute('revision', self.board.data)
		self._set_attribute('no_populate', self.board.data, default=[])
		self._set_attribute('unknown_parts', self.board.data, default=[])
		self._set_attribute('fab_template', self.board.data)
		self._set_attribute('fab_engine', self.board.data)

		#Make sure there are no parts that we don't have information about
		for x in self.unknown_parts:
			self._add_error(x, "Does not have required part information like distributor or manufacturer part numbers")

		#Make sure all parts have enough information to be matchable and placeable
		for variant, lines in self.variants.iteritems():
			for line in lines:
				for part in line:
					if not part.matchable():
						self._add_warning(part.name, "Does not have enough information to be matchable in variant %s" % variant)
					if not part.placeable():
						self._add_warning(part.name, "Does not have enough information to be placeble in variant %s" % variant)

		#Build a set containing all of the parts in all variants so we know what components could be populated but should not be
		self.all_parts = frozenset([x.name for x in self._iterate_all_parts()])
		self._build_lookup_table()

	@return_type("list(string)")
	@param("variant", "string", desc="Assembly variant to consider")
	def nonpopulated_parts(self, variant=None):
		"""
		Fetch the reference identifiers of all parts not populated in this variant.

		The list of strings that is returned does not include parts that are not populated
		in any assembly variant since those are considered to be virtual parts that should
		be ignored.  They are listed in the instance attribute no_populate.
		"""
		parts = frozenset([x.name for x in self._iterate_parts(variant)])

		nopop = self.all_parts - parts
		return [x for x in nopop]

	@return_type("bool")
	def is_clean(self):
		"""
		Return true if there are no errors or warnings about this board.
		"""

		return len(self.errors) == 0 and len(self.warnings) == 0

	@return_type("logical_part")
	@param("reference", "string", "not_empty", desc="Reference identifier to find")
	@param("variant", "string", desc="Assembly variant to search")
	def find(self, reference, variant=None):
		"""
		Find a part on the board using its reference identifier.

		If the same reference identifier refers to different parts in different
		assembly variants, then you must specify which one you want by passing
		the optional variant name.
		"""

		if reference not in self.part_index:
			raise ArgumentError("reference id did not exist", reference=reference)

		matches = self.part_index[reference]
		if len(matches) > 1 and variant is None:
			raise ArgumentError("reference id exists in multiple assembly variants, you must specify one", 
								reference=reference, variants=matches.keys())

		if len(matches) > 1:
			if variant in matches:
				return matches[variant]
			else:
				raise ArgumentError("reference id is not populated in specified assembly variant",
					reference=reference, variants=matches.keys(), specified_variant=variant)

		return matches.values()[0]

	@return_type("list(physical_part)")
	@param("reference", "string", "not_empty", desc="Reference identifier to find")
	@param("variant", "string", desc="Assembly variant to search")
	def lookup(self, reference, variant=None):
		"""
		Use the currently selected matching system to look up a component.

		The data returned can contain realtime price and stock information,
		a list of distributors that carry the part and other details depending
		on the matching system used.
		"""

		matcher = self._get_matcher()
		part = self.find(reference, variant)

		matcher.add_part(part)
		matcher.match_all()

		if not matcher.is_matched(part.name):
			raise DataError("part could not be matched")

		return matcher.match_info(part.name)

	@return_type("bool")
	@param("variant", "string", desc="Assembly variant to search")
	def match_status(self, variant=None):
		"""
		Return whether all parts are matched with a component database
		"""

		results = {}
		matcher = self._get_matcher()

		for part,num in self._iterate_lines(variant):
			if not part.matchable():
				return False

			matcher.add_part(part)

		matcher.match_all()		
		return matcher.all_matched()

	@return_type("map(string, string)")
	@param("variant", "string", desc="Assembly variant to search")
	def match_details(self, variant=None):
		"""
		Attempt to match all BOM components with a component database.

		Return a dictionary mapping reference numbers to matching statuses.
		This function will tell you if any of your parts were not successfully
		matched or did not have enough metadata to match to a unique component.
		"""

		results = {}
		matcher = self._get_matcher()

		for part,num in self._iterate_lines(variant):
			if not part.matchable():
				results[part.name] = 'Insufficient metadata to match'
				continue

			matcher.add_part(part)

		matcher.match_all()
		match_results = matcher.match_details()

		return dict(itertools.chain(results.iteritems(), match_results.iteritems()))

	@param("variant", "string", desc="Assembly variant to update")
	@param("missing_only", "bool", desc="Only update missing metadata attributes")
	def update_all_metadata(self, variant=None, missing=True):
		"""
		Update the entire board with additional metadata from the matching engine.

		This can be used to automatically fill in descriptions, manufacturers and mpns
		if you only have a distributor's part number, for example.  If missing is True,
		the default, only missing data will be added, entered data will not be overwritten.

		If variant is None, all assembly variants are updated.  If variant is passed, then
		only a single variant is updated.
		"""

		if isinstance(variant, basestring):
			update_vars = [self._assure_valid_variant(variant)]
		else:
			update_vars = self.variants.keys()

		handle = self.board.start_update()
		
		for var in update_vars:
			for part in self._iterate_parts(var):
				self.update_metadata(part.name, var, missing, handle=handle)

		self.board.finish_update(handle)

	@param("reference", "string", "not_empty", desc="Reference identifier to find")
	@param("variant", "string", desc="Assembly variant to search")
	@param("missing_only", "bool", desc="Only update missing metadata attributes")
	def update_metadata(self, reference, variant=None, missing=True, handle=None):
		"""
		Update a single part with additional metadata from the matching engine.

		This can be used to automatically fill in descriptions, manufacturers and mpns
		if you only have a distributor's part number, for example.  If missing is True,
		the default, only missing data will be added, entered data will not be overwritten.
		"""

		part = self.find(reference, variant)
		matches = self.lookup(reference, variant)
		if len(matches) > 1:
			raise DataError("part matched multiple times in database", reference=reference, variant=variant, matches=matches)
		
		match = matches[0]

		if match.mpn is not None and (not missing or (missing and part.mpn is None)):
			self.board.set_metadata(part, variant, 'MPN', match.mpn, handle=handle)

		if match.manu is not None and (not missing or (missing and part.manu is None)):
			self.board.set_metadata(part, variant, 'MANU', match.manu, handle=handle)

		if match.desc is not None and (not missing or (missing and part.desc is None)):
			self.board.set_metadata(part, variant, 'DESCRIPTION', match.desc, handle=handle)

	@param("output", "path", desc="Output directory for production files")
	def generate_fab(self, output):
		"""
		Create Gerber,excellon and readme files so this board can be fabricated

		Files are saved into the specified directory output, which is created if
		it does not exist.  A readme.txt file is also generated describing the
		contents of each file.
		"""

		prod = ProductionFileGenerator(self)
		prod.build_fab(output)

	@param("output", "path", desc="Output directory for production files")
	@param("varaint", "string", desc="Assembly variant to process")
	def generate_production(self, output, variant=None):
		"""
		Create Gerber files, BOMs and assembly drawings for this board.
		"""

		variant = self._assure_valid_variant(variant)

		prod = ProductionFileGenerator(self)
		prod.build_production(variant, output)

	@return_type("list(string)")
	def get_errors(self):
		"""
		Return a list of all errors in this board file.
		"""

		return map(self._format_msg, self.errors)

	@return_type("list(string)")
	def get_warnings(self):
		"""
		Return a list of all warnings in this board file.
		"""

		return map(self._format_msg, self.warnings)


	@param('dist', 'string', 'not_empty', desc='a distributor\'s name')
	def require_distributor(self, dist):
		"""
		When searching for prices, require one of these distributors

		This can be called multiple times to whitelist a number of 
		distributors.
		"""

		self.required_dists.append(dist)

	@param('dist', 'string', 'not_empty', desc='a distributor\'s name')
	def exclude_distributor(self, dist):
		"""
		When searching for prices, exclude offerings from this distributor

		This can be called multiple times to blacklist a number of distributors.
		"""

		self.excluded_dists.append(dist)

	@param('packaging', 'string', 'not_empty', desc='a type of packaging')
	def require_packaging(self, packaging):
		"""
		When searching for prices, require a certain type of packaging

		This can be called multiple times to whitelist a number of 
		packaging types like 'Cut Tape' or 'Tape & Reel'.
		"""

		self.required_packages.append(packaging)
	
	@param('packaging', 'string', 'not_empty', desc='a type of packaging')
	def exclude_packaging(self, packaging):
		"""
		When searching for prices, forbid a certain type of packaging

		This can be called multiple times to blacklist a number of 
		packaging types like 'Cut Tape' or 'Tape & Reel'.
		"""

		self.excluded_packages.append(packaging)

	@param("in_stock", "bool", desc="whether parts must be in stock")
	def require_stock(self, in_stock):
		"""
		Set whether parts must be in stock when pricing
		"""

		self.require_stock = in_stock

	@return_type("unit_price")
	@param("ref", "string", desc="part to lookup price information on")
	@param("n", "integer", "nonnegative", desc="number of parts to quote")
	@param("variant", "string", desc="Assembly variant to search")
	@param("total", "bool", desc="Return the total or unit price")
	def price(self, ref, n, variant=None, total=False):
		"""
		Return the best price of n of the part specified by the reference id, ref

		The part prices are searched according to the currently set price model
		including whitelisted and blacklisted packaging types and distributors.
		To find out information about what types of distributors and packaging a
		part is available in, use lookup.
		"""

		part = self.find(ref, variant)
		matcher = self._get_matcher()
		matcher.add_part(part)
		matcher.match_all()

		result = matcher.price_advanced(ref, n, self._build_pricemodel())

		if 'error' in result:
			raise DataError("Could not get price", error=error, result=result)

		if total:
			result['price'] *= n

		return type_system.convert_to_type(result, 'unit_price')

	@return_type("map(string, unit_price)")
	@param("n", "integer", "nonnegative", desc="number of complete boards to quote")
	@param("variant", "string", desc="Assembly variant to price")
	@param("excess", "integer", "nonnegative", desc="percent excess to order of each part")
	def detailed_prices(self, n, excess, variant=None):
		"""
		Return the price and seller for each part that minimizes cost for n boards 

		Optionally order excess percent extra of each part to account for assembly
		losses.
		"""

		quote_quant = n + (excess/100.0)

		out_prices = {line[0].desc: self.price(line[0].name, int(quote_quant*line[1] + 0.5), variant, total=True) for line in self._iterate_lines(variant)}
		return out_prices

	@return_type("map(string, price)")
	@param("n", "integer", "nonnegative", desc="number of complete boards to quote")
	@param("variant", "string", desc="Assembly variant to price")
	@param("excess", "integer", "nonnegative", desc="percent excess to order of each part")
	def total_price(self, n, excess, variant=None):
		"""
		Return the total cost and unit costs of n boards with excess percent excess

		The returned list contains 2 items, the first is the total price, the second
		"""

		prices = self.detailed_prices(n, excess, variant)

		total = Decimal('0.0')

		for price in prices.itervalues():
			total += price.price

		return {'total': total, 'unit': total/n}

	@annotated
	def clear_pricemodel(self):
		"""
		Remove all pricing restrictions
		"""

		self.required_dists = []
		self.excluded_dists = []
		self.required_packages = []
		self.excluded_packages = []
		self.prices = False
		self.require_stock = False
		self.quote_n = 1
		self.quote_quant = 1.0
		self.quote_excess = 0

	@param("quantity", "integer", "positive", desc="number of units to quote")
	@param("excess", "integer", "nonnegative", desc="required excess in %")
	def include_prices(self, quantity, excess):
		"""
		Include prices in generated BOMs
		"""

		self.quote_n = quantity
		self.quote_excess = excess
		self.quote_quant = quantity * (1.0 + excess/100.)
		self.prices = True

	@param("engine", "string", desc="name of component lookup engine to use")
	def set_match_engine(self, engine):
		"""
		Select the service used to lookup components.

		Currently supported values are CacheOnlyMatcher and OctopartMatcher
		to use only cached values or the Octopart API.  Other methods will be 
		supported in the future.
		"""

		if not hasattr(match_engines, engine):
			raise ArgumentError("unknown component matching engine specified", engine=engine)

		matcher = getattr(match_engines, engine)
		if not issubclass(matcher, BOMMatcher):
			raise ArgumentError("invalid component matching engine specified", engine=engine, classname=matcher, object=matcher)

		self._match_engine = matcher

	@return_type("list(bom_line)")
	@param("variant", "string", desc='assembly variant to build')
	def bom_lines(self, variant=None):
		"""
		Get all of the BOM lines for the specified assembly variant
		"""

		variant = self._assure_valid_variant(variant)

		outlines = []
		for line in self._iterate_linegroups(variant):
			outline = type_system.convert_to_type(line, 'bom_line')
			outlines.append(outline)

		return self._order_bom_lines(outlines)

	@return_type("list(string)")
	def get_variants(self):
		return self.variants.keys()

	@param("path", "path", "writeable", desc="The path to the BOM that should be created")
	@param("variant", "string", desc='assembly variant to build')
	@param("format", "string", ("list", ['excel']), desc="The file format that should be saved")
	@param("hide_problems", "bool", desc="do not include errors or warnings processing this file")
	def export_bom(self, path, variant=None, format="excel", hide_problems=False):
		"""
		Expore a Bill of Materials for this board in the specified format.

		BOMs can either be formatted as an industry standard excel spreadsheet
		or using a custom Cheetah based template. Currently only excel spreadsheets
		are supported.  The optional format parameter chooses the format and the 
		result is saved to a file at path.
		"""

		if format == 'excel':
			self._save_excel_bom(variant, path, hide_problems=hide_problems)

	def _save_excel_bom(self, variant, path, hide_problems):
		"""
		Save a BOM in excel format.
		"""

		import xlsxwriter
		import reference

		lib = reference.PCBReferenceLibrary()
		lines = self.bom_lines(variant)

		bk = xlsxwriter.Workbook(path)
		sht = bk.add_worksheet("Bill of Materials")
		
		#formats
		large = bk.add_format({'font_size': 16, 'bold':True})
		med   = bk.add_format({'font_size': 14, 'bold':True})
		bold  = bk.add_format({'bold': True})
		red   = bk.add_format({'bg_color': 'red'})
		orange= bk.add_format({'bg_color': 'orange'})

		#Write header
		sht.write(0, 0, "Bill of Materials", large)
		sht.write(1, 0, self.part, med)
		sht.write(2, 0, self.company)
		sht.write(3, 0, "Revision")
		sht.write(3, 1, self.revision)
		sht.write(4, 0, "Width")
		sht.write(4, 1, self.width)
		sht.write(4, 2, self.units)
		sht.write(5, 0, "Height")
		sht.write(5, 1, self.height)
		sht.write(5, 2, self.units)

		#Write out all of the BOM lines
		headers = ['', 'Qty', 'References', 'Value', 'Footprint', 'Description', 'Manufacturer', 'Part Number', 'Distributor', 'Dist. Part Number']
		row = 7
		col = 0

		for h in headers:
			sht.write(row, col, h, bold)
			col += 1

		row += 1
		for i,line in enumerate(lines):
			sht.write(row, 0, i+1)
			sht.write(row, 1, line.count)
			sht.write(row, 2, ", ".join(line.refs))

			if lib.has_value(line.type):
				sht.write(row, 3, line.value)

			sht.write(row, 4, line.package.name)
			sht.write(row, 5, line.desc)

			if line.manu is not None:
				sht.write(row, 6, line.manu)
			if line.mpn is not None:
				sht.write(row, 7, line.mpn)
			if line.dist is not None:
				sht.write(row, 8, line.dist)
			if line.distpn is not None:
				sht.write(row, 9, line.distpn)

			row += 1

		row += 1

		#Write out all of the unpopulated parts
		sht.write(row, 0, "Unpopulatd Parts", red)
		sht.write(row, 1, ", ".join(self.nonpopulated_parts(variant)), red)

		if not hide_problems:
			row += 2
			if len(self.errors) > 0:
				errors = self.get_errors()
				sht.write(row, 0, "BOM Errors", bold)
				row += 1
				for error in errors:
					sht.write(row, 0, error)
					row += 1

			row += 1
			if len(self.warnings) > 0:
				warnings = self.get_warnings()
				sht.write(row, 0, "BOM Warnings", bold)
				row += 1
				for warning in warnings:
					sht.write(row, 0, warning)
					row += 1

		bk.close()

	def _order_bom_lines(self, lines):
		"""
		Sort bom lines based on the type of each line

		Follow a standard order: R, C, L, D, U, other
		This routine assumes that there will never be more than 100,000
		parts per board, which seems safe for the foreseeable future.
		"""

		order_dict = {'R': 0, 'C': 1, 'L': 2, 'D': 3, 'U': 4}

		def ref_key(line):
			mult = 100000
			ref = line.type
			num = line.lowest
			if ref in order_dict:
				return order_dict[ref]*mult + num

			if ref in ref_key.others:
				return ref_key.others[ref]*mult + num

			ind = ref_key.other_index
			ref_key.others[ref] = ref_key.other_index
			ref_key.other_index += 1
			return ind*mult + num

		ref_key.other_index = 20
		ref_key.others = {}

		return sorted(lines, key=ref_key)

	def _build_pricemodel(self):
		return OfferRequirements(self.required_dists, self.excluded_dists,
								 self.required_packages, self.excluded_packages, 
								 self.require_stock)

	def _default_variant(self):
		"""
		If there is only one variant, choose it by default
		"""

		variants = self.variants.keys()
		if len(variants) == 1:
			return variants[0]

		return None

	def _assure_valid_variant(self, variant):
		"""
		If variant is None, attempt to use the default variant.
		"""

		if variant is None:
			variant = self._default_variant()
			if variant is None:
				raise ArgumentError('you must specify a variant when there is more than one option', variants=self.board.variants.keys())

		return variant

	def _process_variant(self, parts):
		"""
		Group items by unique key and return tuples of identical parts so that you can 
		turn a list of parts into a BOM with identical line items.
		"""

		bomitems = []

		sparts = sorted(parts, key=lambda x:x.unique_id())
		for k,g in itertools.groupby(sparts, lambda x:x.unique_id()):
			bomitems.append(list(g))

		return bomitems

	def _add_warning(self, attribute, msg):
		"""
		Log a warning about something missing or not correct about this circuit board.
		"""

		self.warnings.append(('WARNING', attribute, msg))

	def _add_error(self, attribute, msg):
		"""
		Log an error about something missing or not correct about this circuit board.
		"""

		self.errors.append(('ERROR', attribute, msg))

	def _format_msg(self, msg_tuple):
		"""
		Format an error or warning message into a string
		"""

		return "%s on attribute/part %s: %s" % msg_tuple

	def _set_attribute(self, attribute, data, default="Unknown Attribute", required=True):
		value = default

		if required:
			logger = self._add_error
		else:
			logger = self._add_warning

		if attribute not in data:
			logger(attribute, "Board data did not contain attribute in dictionary")
		else:
			brd_value = data[attribute]
			if brd_value is None:
				logger(attribute, "Attribute was empty or not defined")
			else:
				value = brd_value

		setattr(self, attribute, value)

	def _build_lookup_table(self):
		"""
		Build a map to look up part information given its reference number
		"""

		part_table = {}

		for variant, lines in self.variants.iteritems():
			for line in lines:
				for part in line:
					if part.name not in part_table:
						part_table[part.name] = {}
					
					part_table[part.name][variant] = part

		self.part_index = part_table

	def _iterate_parts(self, variant=None):
		"""
		Iterate over all parts in the assembly variant specified
		"""

		variant = self._assure_valid_variant(variant)
		lines = self.variants[variant]

		for line in lines:
				for part in line:
					yield part

	def _iterate_lines(self, variant=None):
		"""
		Iterate over each distinct BOM line on the board returning
		the first logical part and the number of identical parts
		"""

		variant = self._assure_valid_variant(variant)
		lines = self.variants[variant]

		for line in lines:
			yield line[0], len(line)

	def _iterate_linegroups(self, variant=None):
		"""
		Iterate over all parts grouping them by their bom line

		This returns lists of parts corresponding to each BOM line
		"""

		variant = self._assure_valid_variant(variant)
		lines = self.variants[variant]

		for line in lines:
			yield line

	def _iterate_all_parts(self):
		"""
		Iterate over all parts defined in any assembly variant of this board
		"""

		for variant, lines in self.variants.iteritems():
			for line in lines:
				for part in line:
					yield part

	def _get_matcher(self):
		"""
		Get an instance of the currently supported match engine
		"""

		return self._match_engine()

