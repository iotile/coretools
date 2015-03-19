set -e

source ~/.profile
nosetests -w test

momo help
momo-mod help
momo-mib help
momo-hex help
momo-gsm help
#momo-pcb help #(help currently not supported)
momo-reportinator help
momo-sensor help
momo-multisensor help
#momo-picunit help #(help currently not supported)

sudo chown -R $USER:$USER $MOMOPATH
cd $MOMOPATH
echo "Testing MoMo build..."
echo `pwd`
./tools/automation/build_all.sh
echo "DONE!"