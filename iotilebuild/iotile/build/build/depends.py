"""A class that can resolve product names back to their original location."""

from __future__ import unicode_literals, print_function, absolute_import
from collections import namedtuple
import os
import itertools
from future.utils import viewitems, viewvalues
from iotile.core.dev.iotileobj import IOTile
from iotile.core.exceptions import ArgumentError, BuildError
from .build import ArchitectureGroup


ProductInfo = namedtuple("ProductInfo", ['short_name', 'full_path', 'dependency', 'hidden'])


class ProductResolver(object):
    """This class lets you find the product of a tile or any of its dependencies.

    It internally builds a map of:
        product_type -> product short name -> ProductInfo[]

    Args:
        folder (str): The folder that contains the tile that we wish to inspect.
            If not passed, this is assumed to be the current working directory.
    """

    IGNORED_PRODUCTS = set(['include_directories'])
    _singleton = None

    def __init__(self, folder="."):
        module_settings = os.path.join(folder, 'module_settings.json')

        self._tile = IOTile(folder)
        self._family = ArchitectureGroup(module_settings)
        self._tracking = False
        self._resolved_products = []

        self._create_filter()
        self._create_product_map()

    def _create_filter(self):
        """Create a filter of all of the dependency products that we have selected."""

        self._product_filter = {}

        for chip in itertools.chain(iter(self._family.targets(self._tile.short_name)), iter([self._family.platform_independent_target()])):
            for key, prods in viewitems(chip.property('depends', {})):
                name, _, _ = key.partition(',')

                for prod in prods:
                    if prod not in self._product_filter:
                        self._product_filter[prod] = set()

                    self._product_filter[prod].add(name)

    @classmethod
    def Create(cls):
        """Return a single ProductResolver for the tile at the current working directory."""

        if cls._singleton is None:
            cls._singleton = ProductResolver()

        return cls._singleton

    def _create_product_map(self):
        """Create a map of all products produced by this or a dependency."""

        self._product_map = {}

        for dep in self._tile.dependencies:
            try:
                dep_tile = IOTile(os.path.join('build', 'deps', dep['unique_id']))
            except (ArgumentError, EnvironmentError):
                raise BuildError("Could not find required dependency", name=dep['name'])

            self._add_products(dep_tile)

        self._add_products(self._tile, show_all=True)

    def _add_products(self, tile, show_all=False):
        """Add all products from a tile into our product map."""

        products = tile.products
        unique_id = tile.unique_id
        base_path = tile.output_folder

        for prod_path, prod_type in viewitems(products):
            # We need to handle include_directories and tilebus_definitions
            # specially since those are stored reversed in module_settings.json
            # for historical reasons.  Curently we don't support resolving
            # tilebus_definitions or include_directories in ProductResolver
            if prod_path == 'tilebus_definitions' or prod_path == 'include_directories':
                continue

            if prod_type in self.IGNORED_PRODUCTS:
                continue

            prod_base = os.path.basename(prod_path)
            if prod_type not in self._product_map:
                self._product_map[prod_type] = {}

            prod_map = self._product_map[prod_type]
            if prod_base not in prod_map:
                prod_map[prod_base] = []

            full_path = os.path.normpath(os.path.join(base_path, prod_path))
            info = ProductInfo(prod_base, full_path, unique_id, not show_all and prod_base not in self._product_filter)
            prod_map[prod_base].append(info)

    def find_all(self, product_type, short_name, include_hidden=False):
        """Find all providers of a given product by its short name.

        This function will return all providers of a given product. If you
        want to ensure that a product's name is unique among all dependencies,
        you should use find_unique.

        Args:
            product_type (str): The type of product that we are looking for, like
                firmware_image, library etc.
            short_name (str): The short name of the product that we wish to find,
                usually its os.path.basename()
            include_hidden (bool): Return products that are hidden and not selected
                as visible in the depends section of this tile's module settings.
                This defaults to False.

        Returns:
            list of ProductInfo: A list of all of the matching products.  If no matching
                products are found, an empty list is returned.  If you want to raise
                a BuildError in that case use find_unique.
        """

        all_prods = []

        # If product_type is not return products of all types
        if product_type is None:
            for prod_dict in viewvalues(self._product_map):
                all_prods.extend([prod for prod in prod_dict.get(short_name, []) if include_hidden or not prod.hidden])

            return all_prods

        all_prods = self._product_map.get(product_type, {})
        return [prod for prod in all_prods.get(short_name, []) if include_hidden or not prod.hidden]

    def find_unique(self, product_type, short_name, include_hidden=False):
        """Find the unique provider of a given product by its short name.

        This function will ensure that the product is only provided by exactly
        one tile (either this tile or one of its dependencies and raise a
        BuildError if not.

        Args:
            product_type (str): The type of product that we are looking for, like
                firmware_image, library etc.
            short_name (str): The short name of the product that we wish to find,
                usually its os.path.basename()
            include_hidden (bool): Return products that are hidden and not selected
                as visible in the depends section of this tile's module settings.
                This defaults to False.

        Returns:
            ProductInfo: The information of the one unique provider of this product.
        """

        prods = self.find_all(product_type, short_name, include_hidden)

        if len(prods) == 0:
            raise BuildError("Could not find product by name in find_unique", name=short_name, type=product_type)

        if len(prods) > 1:
            raise BuildError("Multiple providers of the same product in find_unique", name=short_name, type=product_type, products=prods)

        if self._tracking:
            self._resolved_products.append(prods[0])

        return prods[0]

    def start_tracking(self):
        """Start tracking all unique products that have been resolved.

        This is useful for determining the dependencies of a template file
        during a dry run templating for example.
        """

        self._tracking = True
        self._resolved_products = []

    def end_tracking(self):
        """Finish tracking and get a list of all resolved products.

        Returns:
            list of ProductInfo: Every product that was resolved since start
                tracking was last called.
        """

        self._tracking = False
        return self._resolved_products
