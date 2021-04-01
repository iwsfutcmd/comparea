#!/usr/bin/env python3

import json
import sys

assert len(sys.argv) == 2
print json.dumps(json.load(open(sys.argv[1])), indent=2)
