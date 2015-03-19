#!/bin/bash

die() { echo "$@" 1>&2; exit 1; }
set -e

sudo apt-get update
sudo apt-get install -y libc6:i386 lib32stdc++6 gpsim
sudo apt-get install -y python python-dev
sudo apt-get install -y git
wget https://bootstrap.pypa.io/get-pip.py -O - | python

if [ -n "$TRAVIS" ]; then
	PYMOMOROOT=`pwd`
else # VAGRANT
	PYMOMOROOT="/vagrant"
	HOME="/home/vagrant"
fi

cd $HOME
rm -rf ./MoMo-Firmware
git clone https://github.com/welldone/MoMo-Firmware.git

MOMOPATH=$HOME/MoMo-Firmware
cd $MOMOPATH
sudo MOMO_DEV=true SKIP_PYMOMO_INSTALLATION=true MOMOPATH=$MOMOPATH ./tools/automation/provision.sh

echo "MOMOPATH=$MOMOPATH" >> $HOME/.profile

cd $PYMOMOROOT
pip install http://sourceforge.net/projects/scons/files/latest/download --egg | tee -a $HOME/scons-install.log
PYTHONPATH=`cat $HOME/scons-install.log | grep ' library modules ' | awk '{print $6}'`
echo "export PYTHONPATH=$PYTHONPATH" >> $HOME/.profile

pip install -r requirements.txt