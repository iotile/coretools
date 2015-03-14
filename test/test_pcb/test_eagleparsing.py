import unittest
import os.path
from nose.tools import *
from pymomo.exceptions import *
from pymomo.pcb.eagle import part
from pymomo.pcb import CircuitBoard
import tempfile
import shutil
import os

def test_parse_distpn():
	#Board is missing Company and Dimension unit attributes
	board1 = os.path.join(os.path.dirname(__file__), 'eagle', 'controller_missing_attrs.brd')
	board2 = os.path.join(os.path.dirname(__file__), 'eagle', 'controller_dist_distpn.brd')
	b1 = CircuitBoard(board1)
	b2 = CircuitBoard(board2)

	p1 = b1.find('U5')
	p2 = b2.find('U5')

	print str(p1)
	print str(p2)

	assert p1 == p2

def test_assy_vars():
	board = os.path.join(os.path.dirname(__file__), 'eagle', 'assyvars.brd')
	b2 = CircuitBoard(board)
	variants = b2.get_variants()
	print variants

	assert len(variants) == 3
	assert 'VAR1' in variants
	assert 'VAR2' in variants
	assert 'VAR3' in variants

	p1 = b2.find('R1', 'VAR1')
	p2 = b2.find('R1', 'VAR2')

	print p1
	print p2

	assert p1.value == '1K'
	assert p2.value == '25k'

	assert p1.dist == 'Digikey'
	assert p2.dist == 'Digikey'

	assert p1.distpn == '1'
	assert p2.distpn == '2'

@raises(ArgumentError)
def test_assy_nopop():
	board = os.path.join(os.path.dirname(__file__), 'eagle', 'assyvars.brd')
	b2 = CircuitBoard(board)

	b2.find('R1', 'VAR3')

def test_nopop_list():
	board = os.path.join(os.path.dirname(__file__), 'eagle', 'assyvars.brd')
	b2 = CircuitBoard(board)

	p1 = b2.nonpopulated_parts('VAR1')
	p2 = b2.nonpopulated_parts('VAR2')
	p3 = b2.nonpopulated_parts('VAR3')

	assert len(p1) == 0
	assert len(p2) == 0
	assert len(p3) == 1

	assert p3[0] == 'R1'
 
def test_update_attribute():
	board = os.path.join(os.path.dirname(__file__), 'eagle', 'controller_missing_attrs.brd')
	brdcopy = _copy_to_temp(board)

	b = CircuitBoard(brdcopy)

	u5 = b.find('U5')
	assert u5.mpn == None
	assert u5.manu == None

	b.board.set_metadata(u5, None, 'mpn', "test_mpn")
	b.board.set_metadata(u5, None, 'manu', "test_manu")
	b.board.set_metadata(u5, None, 'digikey-pn', "test_digipn")
	bn = CircuitBoard(brdcopy)
	
	u5 = bn.find('U5')
	assert u5.mpn == 'TEST_MPN'
	assert u5.manu == 'TEST_MANU'
	assert u5.distpn == 'TEST_DIGIPN'

	os.remove(brdcopy)

def _copy_to_temp(src):
	dst = tempfile.NamedTemporaryFile(delete=False)

	with open(src, "r+b") as f:
		shutil.copyfileobj(f, dst)

	dst.close()

	return dst.name