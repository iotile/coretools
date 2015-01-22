#dump_fat.py

import sys
import struct

def read_sector(dev, s, num=1):
	dev.seek(s*512)
	return dev.read(512*num)

def readNum(buf, f, offset):
	fmt = '<' + f

	(res,) = struct.unpack_from(fmt, buf, offset=offset)

	return res

def read16(buf, offset):
	return readNum(buf, 'H', offset)

def read32(buf, offset):
	return readNum(buf, 'I', offset)

def read8(buf, offset):
	return readNum(buf, 'B', offset)

def read_fat(dev, sect):
	fmt = '<128I'

	return struct.unpack(fmt, read_sector(dev, sect))

def read_mbr(dev):
	part_fmt = "<B3xB3xII"
	magic_fmt = "<H"
	mbr = read_sector(dev, 0)

	(magic,) = struct.unpack_from(magic_fmt, mbr, offset=510)

	print magic

	if magic != 0xAA55:
		raise ValueError("Invalid MBR Magic Number: 0x%X" % magic)

	parts = [struct.unpack_from(part_fmt, mbr, offset=446+16*x) for x in xrange(0,4)]

	pdicts = []
	for part in parts:
		d = {"first_sector": part[2], "num_sectors": part[3]}
		pdicts.append(d)

	return pdicts

def get_clusterval(dev, cluster, part):
	fat_begin = part['part_start'] + part['num_reserved']

	sect_idx = cluster / (128) + fat_begin
	offset = cluster % (128)

	clusters = read_fat(dev, sect_idx)

	return clusters[offset]

def get_chain(dev, start_cluster):
	fat 

def read_fat32part(dev, offset):
	part = read_sector(dev, offset)

	partinfo = {}

	partinfo['bytes_per_sector'] = read16(part, 0x0B)
	partinfo['sects_per_cluster'] = read8(part, 0x0D)
	partinfo['num_reserved'] 	= read16(part, 0x0E)
	partinfo['num_fats'] = read8(part, 0x10)
	partinfo['sects_per_fat'] = read32(part, 0x24)
	partinfo['root_cluster'] = read32(part, 0x2C)
	partinfo['part_start'] = offset
	partinfo['cluster_start'] = offset + partinfo['num_reserved'] + partinfo['num_fats']*partinfo['sects_per_fat']

	return partinfo	

def read_cluster(dev, cluster, part):
	start_sect = (cluster - 2)*part['sects_per_cluster'] + part['cluster_start']

	return read_sector(dev, start_sect, part['sects_per_cluster'])

def read_dir(dev, cluster, part):
	data = read_cluster(dev, cluster, part)

	dirfmt = '<11sB8xH4xHI'

	numents = len(data) / 32

	ents = []
	for i in xrange(0,numents):
		(name, attrib, clust_high, clust_low, size) = struct.unpack_from(dirfmt, data, offset=32*i)
		if name[0] == '\0':
			continue
		if name[0] == '\xE5':
			continue
		if attrib & 0xF == 0xF:
			continue

		clust = clust_high << 16 | clust_low
		ent = {'name': name, 'cluster': clust, 'size': size, 'attrib': attrib}

		ents.append(ent)

	return ents

def list_cluster_chain(dev, part, start, num=20):
	cluster = start

	for i in xrange(0, num):
		n = get_clusterval(dev, cluster, part)
		print "%d: Cluster 0x%X: 0x%X" % (i+1, cluster, n)

		cluster = n

if len(sys.argv) != 2:
	print "Usage: dump_fat <device>"
	sys.exit(1)

with open(sys.argv[1], "rb", buffering=-1) as dev:
	parts = read_mbr(dev)
	part = parts[0]

	print "Partition 1"
	print "* Start: %d" % part['first_sector']
	print "* Size:  %d sectors" % part['num_sectors']

	f32info = read_fat32part(dev, part['first_sector'])

	ents = read_dir(dev, f32info['root_cluster'], f32info)
	log = ents[0]

	print "Listing chain for file: %s" % log["name"]
	list_cluster_chain(dev, f32info, log["cluster"], num=13)