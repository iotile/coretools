#board.py

import csv
import itertools
from part import Part
from xml.etree import ElementTree
from datetime import date
from octopart.identifier import PartIdentifier
from octopart.octopart import Octopart
from reference import PCBReferenceLibrary
from package import Package

class Board:
	def __init__(self, name, file, variants, partname, width, height, revision, unknown, nopop):
		"""
		Create a Board Object with 1 or more assembly variants from the variant dictionary passed in.
		"""

		self.name = name
		self.file = file
		self.variants = {varname: self._process_variant(var) for (varname,var) in variants.iteritems()}
		self.partname = partname
		self.width = width
		self.height = height
		self.revision = revision
		self.unknown = unknown
		self.no_pop = nopop

	def list_variants(self):
		print "Assembly Variants"

		for k in self.variants.iterkeys():
			print k

	def get_ids(self, variant=None):
		"""
		Return a set containing all of the reference identifiers (C1, R7, etc.) in
		the variant passed, or in all variants if no variant is passed
		"""

		if variant is None:
			vars = self.variants.keys()
		else:
			vars = [variant]

		ids = set()

		for var in vars:
			for line in self.variants[var]:
				refs = map(lambda x: x.name, line)
				ids.update(refs)

		#If we're asked for all of the ids on this board, also include those that
		#may never be populated
		if variant is None:
			ids.update(self.no_pop)

		return ids

	def print_variant(self, key):
		var = self.variants[key]

		print "Variant", key
		for v in var:
			print map(lambda x: x.name, v)

	def get_unique_parts(self):
		parts = {}

		for v in self.variants.iterkeys():
			for line in self.variants[v]:
				part = PartIdentifier(line[0])
				parts[part.build_reference()] = part

		return parts

	def lookup_parts(self):
		parts = self.get_unique_parts()

		op = Octopart()

		self.oracle = op.match_identifiers(parts.values())

	def price_variant(self, variant, multiplier, requirements=None):
		if variant not in self.variants:
			raise ValueError("Invalid variant passed to price_variant")

		self.lookup_parts()
		unmatched = []

		prices = []

		for line in self.variants[variant]:
			id = PartIdentifier(line[0]).build_reference()

			if id not in self.oracle:
				unmatched.append(line)
				continue

			quant = int(len(line)*multiplier + 0.5) #round up
			unit_price = self.oracle[id].best_price(quant, requirements)

			if unit_price is None:
				unmatched.append(line)
				continue

			prices.append((line, unit_price))

		return (prices, unmatched)

	def export_list(self, variant):
		"""
		Return an array with all of the digikey part numbers in this variant so that
		it can be concatenated and used to order parts
		"""

		export = []
		ignored = []

		for line in self.variants[variant]:
			pn = line[0].digipn
			if pn is None or pn == "":
				ignored.append(line[0].name)
				continue

			export += [pn]*len(line)

		print "Ignoring Parts"
		print ignored

		return export

	def variant_data(self, variant, include_costs=False, cost_quantity=1, requirements=None):
		"""
		Return a dictionary describing this variant, suitable for using to fill a template.
		Create an array of BOM line items corresponding to this assembly variant
		"""

		res = {}

		if include_costs:
			self.lookup_parts()
			res['include_costs'] = True
			res['cost_quantity'] = cost_quantity
		else:
			res['include_costs'] = False

		var = self.variants[variant]
		lib = PCBReferenceLibrary()
		today = date.today()

		res['company'] = "WellDone International"
		res['part'] = self.partname
		res['variant'] = variant
		res['revision'] = self.revision
		res['date'] = today.strftime('%x')
		res['lines'] = []
		for line in var:
			num = len(line)
			refs = map(lambda x: x.name, line)
			foot = lib.find_package(line[0].package)[0]
			value = line[0].value
			manu = line[0].manu
			mpn = line[0].mpn
			distpn = line[0].digipn
			dist = ""
			descr = line[0].desc
			if distpn:
				dist = "Digikey"

			unitprice = ""
			lineprice = ""

			if include_costs:
				quantity = num*cost_quantity
				id = PartIdentifier(line[0])
				if id.build_reference() in self.oracle:
					price = self.oracle[id.build_reference()].best_price(quantity, requirements)
					if price is not None:
						unitprice = price[0]
						lineprice = num*unitprice

			ldict = {}
			ldict['qty'] = num
			ldict['refs'] = refs
			ldict['footprint'] = foot
			ldict['value'] = value
			ldict['manu'] = manu
			ldict['mpn'] = mpn
			ldict['dist'] = dist
			ldict['description'] = descr
			ldict['distpn'] = distpn
			ldict['unitprice'] = unitprice
			ldict['lineprice'] = lineprice 
			ldict['pkg_info'] = line[0].pkg_info
			
			res['lines'].append(ldict)

		return res

	def export_bom(self, variant, stream, include_costs=False, cost_quantity=1, requirements=None):
		var = self.variants[variant]

		lib = PCBReferenceLibrary()

		lineno = 1

		today = date.today()

		if include_costs:
			self.lookup_parts()

		if isinstance(stream, str):
			bom = open(stream, "wb")
			close = True
		else:
			bom = stream
			close = False
		
		writ = csv.writer(bom)

		writ.writerow(["WellDone"])
		writ.writerow(["BOM: %s (%s)" % (self.partname, variant)])
		writ.writerow(["Revision: %s" % self.revision])
		writ.writerow(['Date Created: %s' % (today.strftime('%x'))])

		if include_costs:
			writ.writerow(['Costs calculated for %d units' % cost_quantity])

		writ.writerow([])
		writ.writerow([])

		headers = ["Item", "Qty", "Reference Design", "Value", "Footprint", "Description", "Manufacturer", "Manu. Part", "Distributor", "Dist. Part"]
		if include_costs:
			headers += ['Unit Price', 'Line Price']

		writ.writerow(headers)

		for line in var:
			num = len(line)
			refs = ", ".join(map(lambda x: x.name, line))
			foot = lib.find_package(line[0].package)[0]
			value = line[0].value
			manu = line[0].manu
			mpn = line[0].mpn
			distpn = line[0].digipn
			dist = ""
			descr = line[0].desc
			if distpn:
				dist = "Digikey"

			row = [lineno, num, refs, value, foot, descr, manu, mpn, dist, distpn]

			if include_costs:
				quantity = num*cost_quantity
				id = PartIdentifier(line[0])
				if id.build_reference() in self.oracle:
					price = self.oracle[id.build_reference()].best_price(quantity, requirements)
					if price is not None:
						unitprice = price[0]
						lineprice = num*unitprice

						row += [str(unitprice), str(lineprice)]

			writ.writerow(row)

			lineno += 1

		#If there are unpopulated parts, list them here
		unpopulated = self.get_ids() - self.get_ids(variant)

		if len(unpopulated) > 0:
			writ.writerow([])

			s = ", ".join(unpopulated)
			writ.writerow(["Unpopulated Parts", s])

		if close:
			bom.close()

	@staticmethod
	def FromEagle(brd_file):
		"""
		Create a Board from EAGLE Board file by parsing attribute tags embedded with the
		components.  Create different assembly variants for each different configuration
		specified in the file
		"""
		
		tree = ElementTree.parse(brd_file)
		if tree is None:
			raise ValueError("File %s is not a valid XML file" % brd_file)

		root = tree.getroot()

		#Find all of the defined packages in this file
		packages = {x.name: x for x in map(lambda x: Package(x), root.findall('.//package'))}

		elems = root.find("./drawing/board/elements")
		if elems is None:
			raise ValueError("File %s does not contain a list of elements.  This is an invalid board file" % brd_file)

		parts = list(elems)

		unknown = []
		nopop = []
		constant = []
		variable = []
		variants = find_variants(root)

		all_vars = set(variants)

		#Create a part object for each part that has a valid digikey-pn
		#If there are multiple digikey part numbers, create a part for each one
		for part in parts:			
			valid_part = False
			found_vars = set()
			nopop_vars = set()

			for v in variants:
				p,found = Part.FromBoardElement(part, v, packages)
				if p and found:
					variable.append( (v, p) )
					found_vars.add(v)
					valid_part = True
				elif found:
					#If this part has digipn == "" or Populate=no, then it should not be populated in this variant
					valid_part = True
					nopop_vars.add(v)
					nopop.append(part.get('name',"Unknown Name"))

			#See if this is a constant part (with no changes in different variants)
			p,found = Part.FromBoardElement(part, "", packages)
			if p and len(found_vars) == 0 and len(nopop_vars) == 0:
				constant.append(p)
				valid_part = True
			elif p and len(found_vars) != len(all_vars):
				#there are some variants that want the default part and some that want a change
				for var in (all_vars - found_vars) - nopop_vars:
					variable.append( (var, p) )
					valid_part = True

			#Make sure this part has information for at least one assembly variant
			if not valid_part:
				unknown.append(part.get('name',"Unknown Name"))

		vars = {}
		#Create multiple variants
		for var in variants:
			vars[var] = constant + filter_sublists(variable, var)

		return Board("test", 'test', vars,
						partname=find_attribute(root, 'PARTNAME'),
						width=find_attribute(root, 'WIDTH'),
						height=find_attribute(root, 'HEIGHT'),
						revision=find_attribute(root, 'REVISION'),
						unknown=unknown,
						nopop=nopop)

	def _process_variant(self, parts):
		"""
		Group items by unique key and return tuples of identical parts
		"""

		bomitems = []

		sparts = sorted(parts, key=lambda x:x.unique_id())
		for k,g in itertools.groupby(sparts, lambda x:x.unique_id()):
			bomitems.append(list(g))

		return bomitems


def remove_prefix(s, prefix):
	if not s.startswith(prefix):
		return s

	return s[len(prefix):]

def filter_sublists(master, key):
	"""
	Given a list of lists where each of the sublist elements are tuples (key, value),
	return a concatenated list of all values in tuples that match key
	"""

	concat = itertools.chain(master)

	filtered = filter(lambda x: x[0] == key, concat)

	return map(lambda x:x[1], filtered)

def get_variant_id(pn_name):
	known_prefixes = ['DIGIKEY-PN']

	for p in known_prefixes:
		pn_name = remove_prefix(pn_name, p)

	if pn_name.startswith('-'):
		pn_name = pn_name[1:]

	return pn_name

def find_attribute(root, name):
	attr = root.find(".//attribute[@name='%s']" % name)
	if attr is None:
		raise ValueError("Required global board attribute not found: %s" % name)

	return attr.get('value')

def find_variants(root):
	vars = root.findall(".//attribute[@value='%s']" % 'ASSY-VARIANT')

	if len(vars) == 0:
		return ["MAIN"]
	else:
		return map(lambda x: x.get('name'), vars)