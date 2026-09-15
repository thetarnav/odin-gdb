#!/bin/bash

./build.sh

gdb ./main.bin \
     -ex "source odin.py" \
     -ex "break breakpoint" \
     -ex "run" \
     -ex "up"
