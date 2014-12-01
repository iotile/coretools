#pyeagle.py

#Routines that encapsulate the use of EAGLE to automatically generate CAM files
#and assembly drawings.

import shutil
import subprocess
import os.path
import os
from pybom.board import Board
import zipfile
import utilities.config

settings = utilities.config.ConfigFile('settings')

def execute_eagle(args):
	eagle = 'eagle'

	with open(os.devnull, 'wb') as DEVNULL:
		subprocess.check_call([eagle] + args, stdout=DEVNULL, stderr=DEVNULL)

def export_image(board, output, layers):
	process_section(board, output, 'PS', layers)

def process_section(board, output, type, layers):
	"""
	Call the EAGLE program to process a board file and produce a 
	CAM output with the given layers on it.

	@param type can be either "gerber" or "excellon" to generate
	either Gerber 274X files or excellon drill files
	@param output complete path to the output file location
	@param layers the EAGLE layers to include in this CAM file
	@param board the complete path to the board file
	"""

	#Options from EAGLE's built in gerber file for producing 2 layer boards
	#and argument names from EAGLE -? command
	args = ['-X', '-f+', '-c+', '-O+']

	if type == 'gerber':
		args.append('-dGERBER_RS274X')
		remext = '.gpi'
	elif type == 'excellon':
		args.append('-dEXCELLON')
		remext = '.dri'
	elif type == 'PS':
		args.append('-dPS')
		args.append('-h11')
		args.append('-w7.75')
		args.append('-s2.5')
	else:
		raise ValueError("Invalid type specified (must be gerber or excellon), was: %s" % type)

	args.append('-o%s' % output)

	args.append(board)

	for layer in layers:
		args.append(layer)

	execute_eagle(args)

	#if it's gerber, remove gpi file
	#if it's excellon, remove drd file
	if type is not 'PS':
		(base, ext) = os.path.splitext(output)
		remfile = base + remext

		os.remove(remfile)

def process_2layer(board, output_dir, basename, paste=False):
	"""
	Process the eagle file board specified to produce the correct gerber files for
	fabrication and assembly.  All output files will have the same basename with 
	different extensions
	"""

	top_silk = os.path.join(output_dir, basename + '.plc')
	top_copper = os.path.join(output_dir, basename + '.cmp')
	bot_copper = os.path.join(output_dir, basename + '.sol')
	bot_mask = os.path.join(output_dir, basename + '.sts')
	top_mask = os.path.join(output_dir, basename + '.stc')
	drill = os.path.join(output_dir, basename + '.drd')
	top_cream = os.path.join(output_dir, basename + '.crm')

	#Make sure the output dir exists
	ensure_dir_exists(output_dir)

	process_section(board, top_copper, 'gerber', ['Top', 'Pads', 'Vias'])
	process_section(board, bot_copper, 'gerber', ['Bottom', 'Pads', 'Vias'])
	process_section(board, top_silk, 'gerber', ['Dimension', 'tPlace', 'tNames'])
	process_section(board, top_mask, 'gerber', ['tStop'])
	process_section(board, bot_mask, 'gerber', ['bStop'])
	process_section(board, drill, 'excellon', ['Drills', 'Holes'])

	if paste:
		process_section(board, top_cream, 'gerber', ['tCream'])

def ensure_dir_exists(output_dir):
	if not os.path.isdir(output_dir):
		os.makedirs(output_dir)

def create_readme(output_dir, basename, brd_obj, paste=False):
	with open(os.path.join(output_dir, 'README.txt'), "w") as f:
		f.write('WellDone\n')
		f.write("PCB Fabrication Files\n")
		f.write("Name: %s\n" % brd_obj.partname)
		f.write("Revision: %s\n" % brd_obj.revision)
		f.write("Dimensions: %sx%s inches\n" % (brd_obj.width, brd_obj.height))
		f.write("Contact: Tim Burke <tim@welldone.org>\n\n")
		f.write("Folder Contents:\n")
		f.write('%s: Top Silkscreen\n' % (basename+'.plc'))
		f.write('%s: Top Copper\n' % (basename+'.cmp'))
		f.write('%s: Top Soldermask\n' % (basename+'.stc'))
		f.write('%s: Bottom Soldermask\n' % (basename+'.sts'))
		f.write('%s: Bottom Copper\n' % (basename+'.sol'))

		if paste:
			f.write('%s: Top Cream\n' % (basename+'.crm'))

		f.write('%s: Excellon Drill File\n' % (basename+'.drd'))

def build_assembly_drawing(board, output):
	"""
	Create an assembly drawing for this board.  File created will by a PS file
	"""

	export_image(board, output, ['tPlace', 'tNames', 'tDocu', 'Document', 'Reference','Dimension'])

def build_production(board, output_dir, paste=False):
	"""
	Build the set of production files associated with this EAGLE board file.
	Directory structure will be:
	output_dir
		- fabrication
			+ CAM files
			+ README
		- basename_fab.zip
		- assembly
			+ basename_bom.csv
			+ basename_drawing.ps
	"""

	board_obj = Board.FromEagle(board)
		
	basename = board_obj.partname

	fab_dir = os.path.join(output_dir, 'fabrication')
	ass_dir = os.path.join(output_dir, 'assembly')

	#Ensure old fabrication and assembly files are removed
	if os.path.isdir(fab_dir):
		shutil.rmtree(fab_dir)
	if os.path.isdir(ass_dir):
		shutil.rmtree(ass_dir)

	#Create fabrication files
	process_2layer(board, fab_dir, basename, paste=paste)
	create_readme(fab_dir, basename, board_obj, paste=paste)
	zipfab(fab_dir, os.path.join(output_dir, basename + '_fab'))

	#Create assembly files
	ensure_dir_exists(ass_dir)
	build_assembly_drawing(board, os.path.join(ass_dir, basename + '_drawing.ps'))

	#Build a BOM for each assembly variant
	for var in board_obj.variants.keys():
		board_obj.export_bom(var,os.path.join(ass_dir, basename + "_" + var + "_bom.csv"))

def zipfab(path, output):
	"""
	Create a zipfile of the direction path with the name output.zip that will expand into a directory 
	with the same name as output containing all of the files in path. 
	"""
	zip = zipfile.ZipFile(output+'.zip', 'w', zipfile.ZIP_DEFLATED)
	for root, dirs, files in os.walk(path):
		for file in files:
			zip.write(os.path.join(root, file), os.path.join(os.path.basename(output), file))

	zip.close()