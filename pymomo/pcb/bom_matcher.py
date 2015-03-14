#bom_matcher.py
#A generic interface for services that take in identifying information about a
#part and return price offerings for that part.

from pymomo.utilities.typedargs import *
from pymomo.exceptions import *
from partcache import PartCache
import uuid
from decimal import Decimal

class BOMMatcher(object):
	def __init__(self):
		self.requests = []
		self.matched = {}
		self.errors = {}
		self.cache = PartCache()

		self.ref_index = {}

	def _canonicalize_name(self, name):
		"""
		Given a name, like a distributor's name, convert it to
		lowercase and remove all spaces,_ or - characters 
		"""

		return name.lower().replace(' ', '').replace('-', '').replace('_', '')

	def _build_reference(self, part):
		if "distpn" in part:
			return "__SKU__" + self._canonicalize_name(str(part['distpn'])) + self._canonicalize_name(str(part['dist']))

		else:
			mpn = part['mpn']
			manu = part['manu']

			return "__MPN__" + self._canonicalize_name(str(part['mpn'])) + self._canonicalize_name(str(part['manu']))

	@param("mpn", "string", "not_empty", desc="manufacturer's part number")
	@param("manu", "string", desc="manufacturer")
	@param("ref", "string", desc="reference number")
	def add_by_mpn(self, mpn, manu=None, ref=""):
		"""
		Find a part by its manufacturer's part number

		Optionally filter to make sure that the manufacturer is equal to the specified
		'manu' string in case the mpn is not globally unique.  Comparison between
		manufacturer strings, if given, is done in a case insensitive manner after removing
		all - and _ characters from both strings, so e.g. Digi-Key matches digikey.
		
		If ref is given, the returned information will contain the reference number so that
		it can be unambiguously matched with the source that generated the request for pricing
		"""

		part = {'mpn': mpn, 'manu': manu, 'external_ref': ref}
		part['ref'] = self._build_reference(part)

		self.requests.append(part)
		if ref != "":
			self._add_reference(part['ref'], ref)

	@param("distpn", "string", "not_empty", desc="distributor part number")
	@param("dist", "string", desc="distributor name")
	@param("ref", "string", desc="reference identifier")
	def add_by_distpn(self, distpn, dist="", ref=""):
		"""
		Find a part by its distributor part number

		Optionally filter to make sure that the distributor is equal to the specified
		'dist' string in case the distpn is not globally unique.  Comparison between
		distributor strings, if given, is done in a case insensitive manner after removing
		all - and _ characters from both strings, so e.g. Digi-Key matches digikey.

		If ref is given, the returned information will contain the reference number so that
		it can be unambiguously matched with the source that generated the request for pricing
		"""

		part = {'distpn': distpn, 'dist': dist, 'external_ref': ref}
		part['ref'] = self._build_reference(part)

		self.requests.append(part)
		if ref != "":
			self._add_reference(part['ref'], ref)

	@param("part", "logical_part", "matchable", desc="component to look up")
	def add_part(self, part):
		"""
		Find a logical part based on its embedded metadata
		"""

		if part.manu is not None and part.mpn is not None:
			self.add_by_mpn(part.mpn, part.manu, ref=part.name)

			#If we have information about both a distributor and a mpn
			#save both bits of information so that we can filter in case the MPN
			#is not uniquely identifying
			if part.dist is not None:
				self.requests[-1]['require_dist'] = part.dist
			if part.distpn is not None:
				self.requests[-1]['require_distpn'] = part.distpn
		else:
			self.add_by_distpn(part.distpn, part.dist, ref=part.name)

	def _add_reference(self, internal, external):
		if external in self.ref_index:
			raise ArgumentError("attempted to add same reference number twice", reference=external, old=self.ref_index, new=internal)
		
		self.ref_index[external] = internal
	
	@annotated
	def clear(self):
		"""
		Clear all pending requests and results
		"""

		self.requests = []
		self.matched = {}
		self.errors = {}
		self.ref_index = {}

	@annotated
	def match_all(self):
		"""
		Attempt to match all parts.

		Parts that are present in the part cache already are not
		passed on to the matching engine but instead returned directly
		from the cache.  Parts that are uniquely matched are cached 
		for future reference.
		"""

		#Figure out which items are cached
		cache_status = map(lambda x: self.cache.try_get(x['ref']), self.requests)
		uncached = [x[1] for x in enumerate(self.requests) if cache_status[x[0]] is None]

		reqs = [x for x in self.requests]
		self.requests = uncached
		self._match()

		#Perform additional checks to make sure that the match engines are returning
		#just the results that we want and not extras.
		for req in reqs:
			if req['ref'] in self.matched:
				parts = self.matched[req['ref']]

				#Some match engines only match the MPN, not the manufacturer's name, so enforce that here
				if 'manu' in req and req['manu'] is not None:
					self.matched[req['ref']] = filter(lambda x: self._canonicalize_name(req['manu']) == self._canonicalize_name(x.manu), parts)

				#Make sure that if we specified a specific distributor that this part is carried by that distributor
				dist = None
				if 'require_dist' in req:
					dist = req['require_dist']
				if 'dist' in req and req['dist'] is not None:
					dist = req['dist']
				if dist is not None:
					self.matched[req['ref']] = filter(lambda x: self._dist_in_offers(x, dist), parts)

		#Update the cache with the new results
		for key, value in self.matched.iteritems():
			if len(value) == 1:
				self.cache.set(key, value[0])

		#Add in all of the cached results
		for i, x in enumerate(cache_status):
			if x is not None:
				self.matched[reqs[i]['ref']] = [x]

		#Reset the list of requests to include cached and uncached values
		self.requests = reqs

	@return_type("map(string, integer)")
	def match_summary(self):
		"""
		Show which parts have been added, matched or had errors
		"""

		total_reqs = len(self.requests)
		total_matched = len(self.matched)
		total_errors = len(self.errors)

		multimatch = filter(lambda x: len(x) > 1, self.matched.itervalues())
		total_multi = len(multimatch)
		
		ret =  {'Requested Parts': total_reqs, 'Matched Parts': total_matched, 
				'Parts with Errors': total_errors, 'Multiple Matches': total_multi}

		return ret

	@return_type("string")
	def all_matched(self):
		"""
		Check if all requested parts have been matched to exactly 1 physical part
		"""

		if len(self.matched) == len(self.requests):
			multimatch = filter(lambda x: len(x) > 1, self.matched.itervalues())
			total_multi = len(multimatch)

			if total_multi == 0:
				return True

		return False

	@param("reference", "string", "not_empty", desc="reference number")
	@return_type("string")
	def is_matched(self, reference):
		"""
		Check if reference number is matched to a physical part
		"""

		if reference not in self.ref_index:
			return False

		intref = self.ref_index[reference]
		if intref in self.matched:
			return True

		return False

	@return_type("map(string, string)")
	def match_details(self):
		"""
		List the matching status of each part according to its reference number
		"""

		stats = {}

		for r in self.requests:
			refnum = r['ref']
			if 'external_ref' in r and r['external_ref'] != '':
				refnum = r['external_ref']

			if r['ref'] in self.matched:
				if len(self.matched[r['ref']]) == 1:
					stats[refnum] = 'Matched to a unique item'
				else:
					stats[refnum] = '%d separate matches' % (len(self.matched[r['ref']]),)

			elif r['ref'] in self.errors:
				stats[refnum] = self.errors[r['ref']]['msg']
			else:
				stats[refnum] = 'Match has not been attempted'

		return stats

	@param("reference", "string", "not_empty", desc="user reference number")
	@return_type("list(physical_part)")
	def match_info(self, reference):
		"""
		Return matched part info by reference number

		If the part matched multiple items, they are all returned.
		"""

		if reference not in self.ref_index:
			raise ArgumentError("unknown reference number passed", reference=reference)

		intref = self.ref_index[reference]

		if intref not in self.matched:
			raise ArgumentError("part was not matched", reference=reference, internal_reference=intref)

		info = self.matched[intref]

		return info

	@param("quantity", "integer", "positive", desc="requested number of parts")
	@param("reference", "string", "not_empty", desc="reference number")
	@param("seller", "string", desc="required seller of the part")
	@return_type("string")
	def price(self, reference, quantity, seller):
		"""
		Return the best price for N parts from seller as a Decimal
		"""

		info = self.match_info(reference)
		can_seller = self._canonicalize_name(seller)

		if len(info) > 1:
			raise ArgumentError("part is not uniquely matched", reference=reference)

		offers = filter(lambda x: self._canonicalize_name(x.seller)==can_seller, info[0].offers)

		best = Decimal.from_float(1e15)
		for offer in offers:
			price = offer.best_price(quantity)
			if price is not None and price < best:
				best = price

		return best

	def price_advanced(self, reference, quantity, requirements):
		"""
		Find the price of a single item subject to various requirements

		requirements must have a validate function that takes two arguments: an offer and the quantity		
		"""

		info = self.match_info(reference)

		if len(info) > 1:
			return {'error': 'Part not uniquely matched'}

		offers = filter(lambda x: requirements.validate(x, quantity), info[0].offers)

		best = Decimal.from_float(1e15)
		best_offer = None
		for offer in offers:
			price = offer.best_price(quantity)
			if price is not None and price < best:
				best = price
				best_offer = offer

		if best_offer is None:
			return {'error': 'No valid offers found'}
		else:
			return {'price': best, 'offer': offer}

	def prices(self, quantities, requirements):
		"""
		Return the prices for specified parts at specified quantities.

		requirements must have a validate function that takes two arguments: an offer and the quantity
		quantities must be a dictionary mapping reference numbers to quantities 
		"""

		result = {}

		for ref,quantity in self.quantities.iteritems():
			info = self.match_info(ref)

			if len(info) > 1:
				result[ref] = {'error': 'Part not uniquely matched'}
				continue

			offers = filter(lambda x: requirements.validate(x, quantity), info[0].offers)

			best = Decimal.from_float(1e15)
			best_offer = None
			for offer in offers:
				price = offer.best_price(quantity)
				if price is not None and price < best:
					best = price
					best_offer = offer

			if best_offer is None:
				result[ref] = {'error', 'No valid offers found'}
			else:
				result[ref] = {'price': best, 'offer': offer}

		return result

	def _dist_in_offers(self, part, dist):
		"""
		Given a physical_part, make sure it contains an offer from distributor dist
		"""

		dist = self._canonicalize_name(dist)

		for offer in part.offers:
			if self._canonicalize_name(offer.seller) == dist:
				return True

		return False
