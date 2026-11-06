import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("worker", "service", "scripts", "tools"):
    sys.path.insert(0, os.path.join(ROOT, p))
