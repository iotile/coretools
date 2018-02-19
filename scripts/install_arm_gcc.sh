#!/usr/bin/env bash

curl -L -o gcc-arm-none-eabi.tar.gz https://developer.arm.com/-/media/Files/downloads/gnu-rm/7-2017q4/gcc-arm-none-eabi-7-2017-q4-major-linux.tar.bz2?revision=375265d4-e9b5-41c8-bf23-56cbe927e156?product=GNU%20Arm%20Embedded%20Toolchain,64-bit,,Linux,7-2017-q4-major

mkdir -p arm_gcc
tar -jxvf gcc-arm-none-eabi.tar.gz -C arm_gcc --strip-components 1