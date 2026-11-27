---
name: provenance-scoped-literature-graph
description: Build an evidence-backed literature graph, distinguish shared concepts from paper-specific experiments, and query directed relations or two-edge paths across papers. Use for scientific entity alignment, relation extraction, and provenance review.
---

# Provenance-scoped literature graph

## Inventory the supplied corpus

Read `/input/case.json`, the supplied `task.md`, and the actual inputs. Start with `corpus-manifest.json` when present. Match each paper to its own source identifier, DOI, title, authors, version, source hash and license as supplied. Treat alternate formats of one paper as representations of that source. When the aggregate index omits provenance, look back at the individual material files or publisher XML. Keep the supplied JATS paragraph IDs. Use PDF page numbers only when you have real pages.

## Extract claims before merging names

1. From each paper separately, extract entity candidates and directed relations. Give each substantive node and edge an exact quote with `source_id` and `paragraph_id`. Record source conditions, quantity and unit, and direct measurement versus an author interpretation or attributed prior work. Confirm that the quote makes the particular relation; mentioning an entity pair in the same paragraph is weak evidence.
2. Classify generic concepts separately from paper-specific experimental objects. For example, two papers can discuss the same electrode material while using different samples, recipes and test procedures. For each attempted cross-source match, record candidate IDs, decision, and supporting or conflicting evidence. Link a sample to a supported common concept but keep the sample, conditions and observed result paper-specific. Prefer an unresolved candidate when a true equivalence is unknown.
3. Add evidence-backed edges in their original paper contexts. Keep incompatible outcomes as separately sourced edges and explain the limits on comparison. Preserve actual units and distinctions. Check technical particle, formula or symbol syntax against source XML or the original visual instead of guessing from a linearized string.

## Validate and execute graph queries

Python 3.9+ standard library. Build `/app/work/graph.json` with `sources` (each `id` and `passages`, keyed by paragraph ID), `nodes` (each `id`, `label`, `scope`, and `evidence`), `edges` (each `id`, `subject`, `predicate`, `object`, `source_id`, and `evidence`), and `queries`. Evidence entries use `source_id`, `paragraph_id`, and a literal `quote`. A node's scope is the paper ID for a specific object or `concept` for a general entity with evidence from every paper where it is queried.

- For one edge, give a query an `id` and `filters`. `subject`, `predicate`, `object`, and `source_id` use exact equality.
- For a two-edge path, give the query an `id`, `start` node ID, and `path` of exactly two steps. Each step supplies `direction` (`out` follows subject to object, `in` follows object to subject) and nonempty `filters` using the same fields. A path stays within one source unless `allow_cross_source: true`. A source switch is allowed at a shared `concept` that already has evidence in both sources. The resulting path retains each edge's direction, conditions, original source and quote. A shared concept connects the records for comparison. Draw a scientific equivalence or causal conclusion only if separate source evidence supports it.
- Run at least three queries that answer actual case questions. For a cross-paper comparison, report the two source-specific findings and why any difference in conditions matters. Include `no_match` as a gap in this graph. If `truncated` is true, narrow a filter to inspect more results. The helper returns the first 100 matching routes in input edge order.

```sh
python3 /skills/weekly-skill/scripts/query_graph.py /app/work/graph.json --out /app/work/queries.json
```

Start with the single-edge filters. Run one question scoped to each paper and one substantive comparison using a shared predicate or concept. Use a two-edge path only when a question requires one. Inspect `source_coverage` for each paper: it lists the supported nodes, edges and queries that actually retrieved evidence there. If a manifest paper has no record, add its source first. For empty edge or query coverage, return to its passages and complete the graph or report the specific evidence gap. Preserve negative query results.

Copy enough of a passage to include complete values, signs and units. The checker rejects a quotation of “5 mg” inside “15 mg” or “0.5 mg”. Check the experimental conditions and intended direction separately for both papers.

Use the available Python command. The checker rejects unknown node references, wrong-source connections and mismatched quotes. Audit whether each quoted paragraph supports the edge direction and conditions. Recheck merge decisions against original sources and verify that distinct papers are represented. Save the graph and query results in the case's requested files. Reopen `/app/output/result.json` to verify the exact `case_id`, every `output_contract` key, and every referenced file. Record specific gaps due to missing source material, incomparable conditions, unreadable notation, or an unmatched query.

### Illustrative example

For two illustrative experiments pointing to a shared polymer via `studies_material`, start at `sample-a`. Set the first step to `out` with the first paper's `source_id`, and the second to `in` with the second paper's `source_id`. Give both steps the `studies_material` predicate filter and set `allow_cross_source: true`. The result links `sample-a`, the polymer concept, and `sample-b` with two separately cited edges. An absent second relation yields `no_match`.
