import os
import tracemalloc
from pathlib import Path

from mpiperfcli.parser import WorldData

wd = WorldData(Path("./testdata"))
cd = wd.components["mtl"]
before = tracemalloc.take_snapshot()
sizes = [cd.sizes(i) for i in range(10)]
after = tracemalloc.take_snapshot()
diff = after.compare_to(before, "filename")
print("-----------------------------------")
files_to_consider = ['/usr/lib/python3.13/weakref.py:0', os.path.realpath('./mpiperfcli/src/mpiperfcli/parser.py') + ':0']
total_sizes = sum([d.size_diff for d in diff if str(d.traceback) in files_to_consider])
print("total size", total_sizes)
for d in diff:
    if d.size_diff > 0:
        lineno = str(d.traceback)
        print(d.traceback, d.size_diff)
