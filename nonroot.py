#!/usr/bin/env python3
import os
import sys

# Ensure package root is in sys.path
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from nonroot.cli import main

if __name__ == "__main__":
    main()
