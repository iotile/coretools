from  iotile.core.dev.iotileobj import IOTile
import os

def load_tile(name):
	parent = os.path.dirname(__file__)
	path = os.path.join(parent, name)

	return IOTile(path)

def test_load_releasemode():
	tile = load_tile('releasemode_component')

	assert tile.release == True
	assert tile.short_name == 'tile_gpio'
	assert tile.output_folder == tile.folder

def test_load_devmode():
	tile = load_tile('devmode_component')

	assert tile.release == False
	assert tile.short_name == 'tile_gpio'
	assert tile.output_folder != tile.folder

def test_load_oldstyle():
	tile = load_tile('oldstyle_component')

	assert tile.release == False
	assert tile.short_name == 'tile_gpio'
	assert tile.output_folder != tile.folder
