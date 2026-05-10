#!/usr/bin/env python3
"""
Parse all skills from skills_lib -> generate graph.json for D3.js visualization.

Nodes: one per skill (id, label, description, cluster, capabilities, requirements, degree)
Edges:
  - "related"    : explicit "works well with / related skills" mentions in SKILL.md
  - "shared-tag" : skills sharing >=3 capability/requirement keywords

Note: SKILLS_LIB path must be set to your local skills library.
"""

import json
import re
import os
from pathlib import Path
from collections import defaultdict
from itertools import combinations

# ── Config — update to your local path ───────────────────────
SKILLS_LIB    = Path(os.environ.get("SKILLS_LIB_PATH", "skills_lib"))
SKILLS_INDEX  = SKILLS_LIB / "skills_index.json"
BUNDLES_FILE  = SKILLS_LIB / "data" / "bundles.json"
SKILLS_DIR    = SKILLS_LIB / "skills"
OUT_FILE      = Path(__file__).parent / "graph.json"

SHARED_TAG_MIN   = 3
MAX_SHARED_EDGES = 15

STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "are", "was", "use",
    "using", "used", "can", "you", "your", "when", "how", "all", "any", "each",
    "into", "via", "best", "new", "get", "set", "run", "add", "make", "help",
    "build", "work", "works", "based", "need", "needs", "tool", "tools",
    "skill", "skills", "system", "systems", "support", "handling",
    "including", "include", "includes", "provide", "provides", "enable",
    "enables", "allow", "allows", "ensure", "ensures", "manage", "manages",
    "create", "creates", "define", "defines", "design", "designs",
    "implement", "implements", "setup", "configure", "test", "testing",
    "deploy", "deployment", "pattern", "patterns", "approach", "approaches",
    "practice", "practices", "guide", "guides", "method", "methods",
}


def parse_skill_md(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"capabilities": [], "requirements": [], "related": []}

    capabilities, requirements, related = [], [], []
    current_section = None

    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^##\s+capabilities", stripped, re.IGNORECASE):
            current_section = "capabilities"
        elif re.match(r"^##\s+requirements?", stripped, re.IGNORECASE):
            current_section = "requirements"
        elif re.match(r"^##\s+(related skills?|works well with)", stripped, re.IGNORECASE):
            current_section = "related"
        elif re.match(r"^##\s+", stripped):
            current_section = None

        if current_section in ("capabilities", "requirements") and stripped.startswith("-"):
            item = stripped.lstrip("- ").strip().lower()
            if item:
                (capabilities if current_section == "capabilities" else requirements).append(item)

        if current_section == "related":
            found = re.findall(r"`([a-z][a-z0-9\-]+)`", stripped)
            related.extend(found)
            if stripped.startswith("-"):
                item = stripped.lstrip("- ").strip()
                if re.match(r"^[a-z][a-z0-9\-]+$", item):
                    related.append(item)

        m = re.search(r"works well with[:\s]+(.+)", stripped, re.IGNORECASE)
        if m:
            related.extend(re.findall(r"`([a-z][a-z0-9\-]+)`", m.group(1)))

    return {"capabilities": capabilities, "requirements": requirements, "related": list(set(related))}


def tokenize(items: list[str], description: str = "") -> set[str]:
    tokens = set()
    all_text = " ".join(items) + " " + description
    words = re.split(r"[\s\-/,\.:()\'\`]+", all_text.lower())
    for w in words:
        if len(w) > 3 and w not in STOPWORDS and w.isalpha():
            tokens.add(w)
    for item in items:
        normalized = re.sub(r"[\s/]+", "-", item.lower().strip())
        if len(normalized) > 4 and "-" in normalized:
            tokens.add(normalized[:40])
    return tokens


def build_cluster(skill_id: str, skill_bundles: dict, category: str) -> str:
    bundles = skill_bundles.get(skill_id, [])
    if bundles:
        return bundles[0]
    if category and category != "uncategorized":
        return category
    return "other"


def main():
    print("Loading index...")
    with open(SKILLS_INDEX, encoding="utf-8") as f:
        index = json.load(f)

    print("Loading bundles...")
    with open(BUNDLES_FILE, encoding="utf-8") as f:
        bundles_raw = json.load(f)["bundles"]

    skill_bundles: dict[str, list[str]] = defaultdict(list)
    for bname, bdata in bundles_raw.items():
        for s in bdata["skills"]:
            skill_bundles[s].append(bname)

    valid_ids = {s["id"] for s in index}

    print(f"Parsing {len(index)} skills...")
    nodes, skill_data = [], {}

    for i, entry in enumerate(index):
        sid = entry["id"]
        skill_path = SKILLS_LIB / entry["path"] / "SKILL.md"
        parsed  = parse_skill_md(skill_path) if skill_path.exists() else {"capabilities": [], "requirements": [], "related": []}
        cluster = build_cluster(sid, skill_bundles, entry.get("category", ""))
        tokens  = tokenize(parsed["capabilities"] + parsed["requirements"], entry.get("description", ""))

        node = {
            "id": sid, "label": entry.get("name", sid),
            "description": entry.get("description", ""),
            "cluster": cluster, "category": entry.get("category", "uncategorized"),
            "source": entry.get("source", ""),
            "capabilities": parsed["capabilities"], "requirements": parsed["requirements"],
            "related_raw": parsed["related"], "_tokens": tokens,
        }
        nodes.append(node)
        skill_data[sid] = node
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(index)} parsed")

    print("Building edges...")
    edges, edge_set = [], set()

    def add_edge(src, tgt, etype, weight=1.0):
        key = (min(src, tgt), max(src, tgt), etype)
        if key not in edge_set and src != tgt:
            edge_set.add(key)
            edges.append({"source": src, "target": tgt, "type": etype, "weight": weight})

    for node in nodes:
        for ref in node["related_raw"]:
            if ref in valid_ids:
                add_edge(node["id"], ref, "related", 3.0)

    token_index: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        for token in node["_tokens"]:
            token_index[token].append(node["id"])

    pair_shared: dict[tuple, int] = defaultdict(int)
    for token, skill_ids in token_index.items():
        if len(skill_ids) > 1:
            for a, b in combinations(skill_ids[:100], 2):
                pair_shared[(min(a, b), max(a, b))] += 1

    node_shared_count: dict[str, int] = defaultdict(int)
    for (a, b), count in sorted(pair_shared.items(), key=lambda x: -x[1]):
        if count < SHARED_TAG_MIN:
            break
        if node_shared_count[a] >= MAX_SHARED_EDGES or node_shared_count[b] >= MAX_SHARED_EDGES:
            continue
        add_edge(a, b, "shared-tag", min(count / 5.0, 2.0))
        node_shared_count[a] += 1
        node_shared_count[b] += 1

    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    output_nodes = [{
        "id": n["id"], "label": n["label"], "description": n["description"],
        "cluster": n["cluster"], "category": n["category"], "source": n["source"],
        "capabilities": n["capabilities"], "requirements": n["requirements"],
        "related": [r for r in n["related_raw"] if r in valid_ids],
        "degree": degree[n["id"]],
    } for n in nodes]

    clusters = defaultdict(int)
    for n in output_nodes:
        clusters[n["cluster"]] += 1

    graph = {
        "meta": {"total_nodes": len(output_nodes), "total_edges": len(edges), "clusters": dict(clusters)},
        "nodes": output_nodes,
        "edges": edges,
    }

    print(f"Writing {OUT_FILE}...")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Done. {len(output_nodes)} nodes, {len(edges)} edges")


if __name__ == "__main__":
    main()
