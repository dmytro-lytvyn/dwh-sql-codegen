#!/bin/bash

set -e

CURRENT_DIR="$(dirname "$0")"
cd ${CURRENT_DIR}

/Applications/Wine.app/Contents/Resources/bin/wine ~/.wine/drive_c/Python27/python.exe ./ETL_CodeGen.py
