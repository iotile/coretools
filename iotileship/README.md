# IOTileShip
A python package for shipping IOTile products.

## Installation

```
pip install iotile-ship
```

## Sample Use Case:

Python Script
```
rm = RecipeManager()
rm.add_recipe_folder('path_to_recipes')
recipe = rm.get_recipe('recipe_name')
recipe.run()
```

Command line
```
iotile-ship test_recipe --uuid 0x98
```

## Copyright and license
This code is adapted from code and documentation copyright 2015 WellDone International as pymomo. The IOTile package is released under the [LGPLv3](https://www.gnu.org/licenses/lgpl.html) Open Source license.  See the LICENSE file.

`iotile-ship` redistributes SCons.  More information on SCons can be found at http://scons.org