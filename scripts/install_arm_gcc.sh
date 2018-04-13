#!/usr/bin/env bash

set -e

rm -rf arm_gcc
rm -rf arm_qemu

curl -L -o gcc-arm-none-eabi.tar.gz https://s3.amazonaws.com/arch-public-static-files-11ca2993de6b03471b7b1f1f704cb58f/gcc-arm-none-eabi-7-2017-q4-major-linux.tar.bz2
mkdir -p arm_gcc
tar -jxf gcc-arm-none-eabi.tar.gz -C arm_gcc --strip-components 1
rm gcc-arm-none-eabi.tar.gz

curl -L -o qemu.tar.gz https://s3.amazonaws.com/arch-public-static-files-11ca2993de6b03471b7b1f1f704cb58f/gnuarmeclipse-qemu-debian64-2.8.0-201612271623-dev.tgz
mkdir -p arm_qemu
tar -zxf qemu.tar.gz -C arm_qemu --strip-components 2
rm qemu.tar.gz
