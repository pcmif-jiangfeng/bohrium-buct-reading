"""Validate and query evidence-backed edges and nodes in a literature graph."""

import argparse
import json
from pathlib import Path
import unicodedata


QUERY_FIELDS = {"subject", "object", "predicate", "source_id"}


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected nonempty text")
    return " ".join(unicodedata.normalize("NFC", value).split())


def records(rows):
    by_id = {}
    for row in rows:
        identifier = text(row["id"])
        if identifier in by_id:
            raise ValueError(f"duplicate ID: {identifier}")
        by_id[identifier] = row
    return by_id


def verify_evidence(owner, sources):
    verified_sources = set()
    if not owner["evidence"]:
        raise ValueError(f"{owner['id']}: missing evidence")
    for evidence in owner["evidence"]:
        source_id = text(evidence["source_id"])
        paragraph = text(evidence["paragraph_id"])
        source = sources.get(source_id)
        passage = source["passages"].get(paragraph) if source else None
        if passage is None or text(evidence["quote"]) not in text(passage):
            raise ValueError(f"{owner['id']}: quote does not match {source_id}/{paragraph}")
        verified_sources.add(source_id)
    return verified_sources


def run(graph):
    sources = records(graph["sources"])
    nodes = records(graph["nodes"])
    edges = records(graph["edges"])
    queries = records(graph["queries"])
    if not sources or "concept" in sources or not nodes or not queries:
        raise ValueError("sources, nodes and queries are required; concept is reserved for node scope")

    node_sources = {}
    for node_id, node in nodes.items():
        text(node["label"])
        scope = text(node["scope"])
        supports = verify_evidence(node, sources)
        if scope != "concept" and supports != {scope}:
            raise ValueError(f"{node_id}: instance evidence must match its source scope")
        node_sources[node_id] = supports

    for edge_id, edge in edges.items():
        source_id = text(edge["source_id"])
        text(edge["predicate"])
        if verify_evidence(edge, sources) != {source_id}:
            raise ValueError(f"{edge_id}: edge evidence must match its source scope")
        for field in ("subject", "object"):
            node_id = text(edge[field])
            if node_id not in node_sources or source_id not in node_sources[node_id]:
                raise ValueError(f"{edge_id}: node {node_id} lacks evidence in source {source_id}")

    results = []
    for query_id, query in queries.items():
        filters = query["filters"]
        if not isinstance(filters, dict) or not filters or set(filters) - QUERY_FIELDS:
            raise ValueError(f"{query_id}: supply recognized, nonempty filters")
        filters = {field: text(value) for field, value in filters.items()}
        matches = [edge for edge in edges.values() if all(text(edge[field]) == value for field, value in filters.items())]
        matched_nodes = dict.fromkeys(text(edge[field]) for edge in matches for field in ("subject", "object"))
        results.append({
            "id": query_id, "filters": filters, "status": "matched" if matches else "no_match",
            "edges": matches, "nodes": [nodes[node_id] for node_id in matched_nodes],
        })
    return {"sources": len(sources), "nodes": len(nodes), "edges": len(edges), "queries": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.graph.resolve() == args.out.resolve():
            raise ValueError("input and output paths must differ")
        result = run(json.loads(args.graph.read_text(encoding="utf-8-sig")))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: (len(value) if key == "queries" else value) for key, value in result.items()}))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
