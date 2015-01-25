#octopart.py
#Wrapper arround Octopart REST API

import os
import json
import urllib
from pymomo.pcb.bom_matcher import BOMMatcher
from pymomo.utilities.typedargs import *
from pymomo.exceptions import *

@context()
class OctopartMatcher (BOMMatcher):
	"""
	A service for pricing parts using the Octopart API.

	Currently parts can be matched using either a distributor's name and part number
	or directly using manufacturer's part numbers and the manufacturer's 
	name.  Realtime pricing information is returned as are any errors
	during the matching process. 
	"""

	URL = 'http://octopart.com/api/v3/'

	@param("key", "string", desc="Octopart API Key")
	def __init__(self, key=None):
		super(OctopartMatcher, self).__init__()

		if key is not None:
			self.api_key = key
		elif 'OCTOPART_KEY' in os.environ:
			self.api_key = os.environ['OCTOPART_KEY']
		else:
			raise ArgumentError('You need to either specify an Octopart API Key or have the OCTOPART_KEY environment variable set')

	def _build_call(self, method, args):
		"""
		Build a URL call with arg=val pairs including the apikey to the url specifying the method
		given.
		"""

		url = OctopartMatcher.URL + method + '?'

		out_args = []
		out_args.extend(args)
		out_args.append(('apikey', self.api_key))
		out_args.append(('include[]', 'short_description'))
		out_strings = map(lambda x: urllib.quote(x[0])+'='+urllib.quote(x[1]), out_args)

		query_string = "&".join(out_strings)

		return url + query_string

	def _build_query(self, part):
		query = {}
		if "distpn" in part:
			query['sku'] = part["distpn"]
		elif "mpn" in part:
			query['mpn'] = part["mpn"]
		else:
			raise ArgumentError("Octopart API cannot match a part without either a digikey part number or a manufacturer's part number", part=part)
		
		query['reference'] = part['ref']
		return query

	def _call(self, url):
		data = urllib.urlopen(url).read()
		response = json.loads(data)

		return response

	def _call_method(self, method, args):
		url = self._build_call(method, args)
		return self._call(url)

	def _build_offer(self, resp):
		"""
		Create a part_offer from an octopart api response
		"""

		offer = {}
		offer['seller'] = resp['seller']['name']
		offer['moq'] = resp['moq']
		offer['stock_quantity'] = resp['in_stock_quantity']
		offer['packaging'] = resp['packaging']
		offer['breaks'] = self._build_breaks(resp['prices'])

		return type_system.convert_to_type(offer, 'part_offer')

	def _build_breaks(self, resp):
		"""
		Create a price_list object from an octopart API response
		"""

		if 'USD' in resp:
			return type_system.convert_to_type(resp['USD'], 'price_list')

		return type_system.convert_to_type([], 'price_list')

	def _build_part(self, response):
		"""
		Create a physical_part object from an octopart api response
		"""

		part = {}

		manuname = ""
		if 'name' in response['manufacturer']:
			manuname = response['manufacturer']['name']

		part['manu'] = manuname
		part['mpn'] = response['mpn']
		
		part['desc'] = response['short_description']
 
		offers = map(lambda x: self._build_offer(x), response['offers'])
		part['offers'] = offers
		
		return type_system.convert_to_type(part, 'physical_part')

	def _match(self):
		for i in xrange(0, len(self.requests), 20):
			req = self.requests[i:i+20]
			queries = map(lambda x: self._build_query(x), req)

			query = json.dumps(queries)

			resp = self._call_method('parts/match',[('queries',query), ('exact_only', 'true')])

			for result in resp['results']:
				ref = result['reference']

				if len(result['items']) == 0:
					self.errors[ref] = {'msg': 'Did not match'}
					continue

				parts = map(lambda x: self._build_part(x), result['items'])
				self.matched[ref] = parts
