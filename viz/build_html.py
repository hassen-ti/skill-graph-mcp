#!/usr/bin/env python3
"""Embed graph.json into index.html for true standalone use."""

import json
from pathlib import Path

HERE = Path(__file__).parent
GRAPH_JSON = HERE / "graph.json"
TEMPLATE   = HERE / "index_template.html"
OUTPUT     = HERE / "index.html"

with open(GRAPH_JSON, encoding="utf-8") as f:
    graph_data = f.read()

with open(TEMPLATE, encoding="utf-8") as f:
    html = f.read()

html = html.replace("__GRAPH_DATA_PLACEHOLDER__", graph_data)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)

size_kb = OUTPUT.stat().st_size / 1024
print(f"Built {OUTPUT} ({size_kb:.0f} KB)")
