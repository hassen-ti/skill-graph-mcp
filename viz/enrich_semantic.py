#!/usr/bin/env python3
"""
Enrich graph.json with semantic data from Neo4j.

Steps:
  1. Export skill embeddings from Neo4j
  2. KMeans community detection on normalized embeddings
  3. UMAP 1536D -> 2D positions
  4. Inject umap_x, umap_y, community into existing graph.json nodes
  5. Rebuild index.html

Requires: umap-learn scikit-learn neo4j numpy
  pip install umap-learn scikit-learn neo4j numpy
"""

import json
import subprocess
import numpy as np
from pathlib import Path
from neo4j import GraphDatabase
from sklearn.cluster import KMeans
import umap as umap_lib

# ── Config ────────────────────────────────────────────────────
NEO4J_URI   = "bolt://localhost:7687"
NEO4J_USER  = "neo4j"
NEO4J_PASS  = "skillgraph"

N_CLUSTERS  = 18   # target number of semantic communities

HERE       = Path(__file__).parent
GRAPH_JSON = HERE / "graph.json"

# ── 1. Export embeddings ──────────────────────────────────────
def export_embeddings():
    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        result = session.run(
            "MATCH (s:Skill) WHERE s.embedding IS NOT NULL "
            "RETURN s.id AS id, s.embedding AS embedding"
        )
        data = {r["id"]: r["embedding"] for r in result}
    driver.close()
    print(f"  {len(data)} skills with embeddings")
    return data

# ── 2. Normalize embeddings ───────────────────────────────────
def normalize(vecs):
    mat   = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return mat / np.maximum(norms, 1e-10)

# ── 3. KMeans community detection ─────────────────────────────
def run_kmeans(mat, n_clusters):
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    return km.fit_predict(mat).tolist()

# ── 4. UMAP ───────────────────────────────────────────────────
def run_umap(vecs):
    print("Running UMAP (this takes ~30s)...")
    reducer = umap_lib.UMAP(n_components=2, random_state=42,
                            n_neighbors=15, min_dist=0.1)
    coords  = reducer.fit_transform(np.array(vecs, dtype=np.float32))
    lo, hi  = coords.min(axis=0), coords.max(axis=0)
    return (coords - lo) / np.maximum(hi - lo, 1e-8)

# ── Main ──────────────────────────────────────────────────────
def main():
    embedding_map = export_embeddings()

    print("Loading graph.json...")
    with open(GRAPH_JSON, encoding="utf-8") as f:
        graph = json.load(f)

    nodes_with_emb = [n for n in graph["nodes"] if n["id"] in embedding_map]
    missing        = len(graph["nodes"]) - len(nodes_with_emb)
    if missing:
        print(f"  WARNING: {missing} nodes have no embedding — kept as-is")

    ids  = [n["id"] for n in nodes_with_emb]
    vecs = [embedding_map[sid] for sid in ids]

    print("Normalizing embeddings...")
    mat = normalize(vecs)

    print(f"Running KMeans (n_clusters={N_CLUSTERS})...")
    communities = run_kmeans(mat, N_CLUSTERS)
    print(f"  {N_CLUSTERS} communities")

    coords = run_umap(mat)

    idx_of = {sid: i for i, sid in enumerate(ids)}

    print("Enriching nodes...")
    for node in graph["nodes"]:
        i = idx_of.get(node["id"])
        if i is not None:
            node["community"] = communities[i]
            node["umap_x"]    = round(float(coords[i, 0]), 5)
            node["umap_y"]    = round(float(coords[i, 1]), 5)
        else:
            node["community"] = -1
            node["umap_x"]    = None
            node["umap_y"]    = None

    graph["meta"]["n_communities"] = N_CLUSTERS

    print("Writing graph.json...")
    with open(GRAPH_JSON, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, separators=(",", ":"))

    print("Rebuilding index.html...")
    subprocess.run(["python", str(HERE / "build_html.py")], check=True)

    print(f"\nDone — {N_CLUSTERS} communities, {len(ids)} nodes enriched.")

if __name__ == "__main__":
    main()
