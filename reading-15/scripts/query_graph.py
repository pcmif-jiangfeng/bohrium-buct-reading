"""Validate and query evidence-backed edges and nodes in a literature graph."""

import argparse
from collections import defaultdict
from itertools import islice
import json
from pathlib import Path
import unicodedata


QUERY_FIELDS = {"subject", "object", "predicate", "source_id"}
DIRECTIONS = {"out": ("subject", "object"), "in": ("object", "subject")}
MAX_ROUTES = 100


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


def query_filters(owner, filters):
    if not isinstance(filters, dict) or not filters or set(filters) - QUERY_FIELDS:
        raise ValueError(f"{owner}: supply recognized, nonempty filters")
    return {field: text(value) for field, value in filters.items()}


def edge_matches(edge, filters):
    return all(text(edge[field]) == value for field, value in filters.items())


def query_path(query_id, query, edges, nodes):
    start = text(query["start"])
    allow_switch = query.get("allow_cross_source", False)
    if start not in nodes or type(allow_switch) is not bool or "filters" in query:
        raise ValueError(f"{query_id}: provide a valid start, a Boolean allow_cross_source and per-step filters")
    path = query["path"]
    if not isinstance(path, list) or len(path) != 2:
        raise ValueError(f"{query_id}: a path has exactly two steps")
    steps = []
    for step in path:
        direction = text(step["direction"])
        if direction not in DIRECTIONS:
            raise ValueError(f"{query_id}: direction must be out or in")
        steps.append({"direction": direction, "filters": query_filters(query_id, step["filters"])})
    (first_in, first_out), (second_in, second_out) = (DIRECTIONS[step["direction"]] for step in steps)

    def may_switch(middle):
        return allow_switch and text(nodes[middle]["scope"]) == "concept"

    # Index the second hop by the middle node and by source when switching is disallowed.
    second_hops = defaultdict(list)
    for key, edge in edges.items():
        if edge_matches(edge, steps[1]["filters"]):
            middle, source = text(edge[second_in]), text(edge["source_id"])
            second_hops[middle, None if may_switch(middle) else source].append((key, edge))

    def routes():
        for key, edge in edges.items():
            if text(edge[first_in]) != start or not edge_matches(edge, steps[0]["filters"]):
                continue
            middle, source = text(edge[first_out]), text(edge["source_id"])
            for next_key, next_edge in second_hops.get((middle, None if may_switch(middle) else source), ()):
                if key != next_key:
                    yield {"node_ids": [start, middle, text(next_edge[second_out])], "edge_ids": [key, next_key],
                           "source_ids": [source, text(next_edge["source_id"])]}

    matches = list(islice(routes(), MAX_ROUTES + 1))
    kept = matches[:MAX_ROUTES]
    return {"id": query_id, "start": start, "path": steps, "allow_cross_source": allow_switch,
            "status": "matched" if kept else "no_match", "truncated": len(matches) > MAX_ROUTES, "routes": kept,
            "edges": [edges[key] for key in dict.fromkeys(key for route in kept for key in route["edge_ids"])],
            "nodes": [nodes[key] for key in dict.fromkeys(key for route in kept for key in route["node_ids"])]}


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
        if "path" in query:
            results.append(query_path(query_id, query, edges, nodes))
            continue
        filters = query_filters(query_id, query["filters"])
        matches = [edge for edge in edges.values() if edge_matches(edge, filters)]
        matched_nodes = dict.fromkeys(text(edge[field]) for edge in matches for field in ("subject", "object"))
        results.append({
            "id": query_id, "filters": filters, "status": "matched" if matches else "no_match",
            "edges": matches, "nodes": [nodes[node_id] for node_id in matched_nodes],
        })
    coverage = {}
    for source_id in sources:
        coverage[source_id] = {
            "node_ids": [key for key, support in node_sources.items() if source_id in support],
            "edge_ids": [key for key, edge in edges.items() if text(edge["source_id"]) == source_id],
            "matching_query_ids": [row["id"] for row in results
                                   if any(text(edge["source_id"]) == source_id for edge in row["edges"])],
        }
    return {"sources": len(sources), "nodes": len(nodes), "edges": len(edges), "queries": results,
            "source_coverage": coverage}


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
