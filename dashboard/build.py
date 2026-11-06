"""
build.py: embeds dashboard/data.json into dashboard/template.html and writes
dashboard/index.html (a single file; opens by double-click, no server needed).
Run after etl/run_analysis.py.
"""
import json

with open("data.json") as f:
    data = json.load(f)
with open("template.html") as f:
    template = f.read()
with open("index.html", "w") as f:
    f.write(template.replace("__DATA_JSON__", json.dumps(data, separators=(",", ":"))))
print("wrote index.html")
