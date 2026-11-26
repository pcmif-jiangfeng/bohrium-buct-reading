---
name: provenance-scoped-literature-graph
description: Build a queryable graph from supplied research papers, preserve source-specific experiment identities, and attach exact passage evidence to every node and edge. Use for cross-paper scientific entity and relation extraction with provenance.
---

# Provenance-scoped literature graph

## Inventory the supplied corpus

Read `/input/case.json`, the supplied `task.md`, and the actual inputs. Start with `corpus-manifest.json` when present. Match each paper to its own source identifier, DOI, title, authors, version, source hash and license as supplied. Treat alternate formats of one paper as representations of that source. When the aggregate index omits provenance, look back at the individual material files or publisher XML. Keep the supplied JATS paragraph IDs. Use PDF page numbers only when you have real pages.

## Extract claims before merging names

1. From each paper separately, extract entity candidates and directed relations. Give each substantive node and edge an exact quote with `source_id` and `paragraph_id`. Record source conditions, quantity and unit, and direct measurement versus an author interpretation or attributed prior work. Confirm that the quote makes the particular relation; mentioning an entity pair in the same paragraph is weak evidence.
2. Classify generic concepts separately from paper-specific experimental objects. For example, two papers can discuss the same electrode material while using different samples, recipes and test procedures. For each attempted cross-source match, record candidate IDs, decision, and supporting or conflicting evidence. Link a sample to a supported common concept but keep the sample, conditions and observed result paper-specific. Prefer an unresolved candidate when a true equivalence is unknown.
3. Add evidence-backed edges in their original paper contexts. Keep incompatible outcomes as separately sourced edges and explain the limits on comparison. Preserve actual units and distinctions. Check technical particle, formula or symbol syntax against source XML or the original visual instead of guessing from a linearized string.

## Validate and execute graph queries

Python 3.9+ standard library. Build a separate `/app/work/graph.json` work file with `sources` (each `id` plus `passages`, a paragraph-ID-to-text object), `nodes` (each `id`, `label`, `scope`, and `evidence`), `edges` (each `id`, `subject`, `predicate`, `object`, `source_id`, and `evidence`), and `queries` (each `id` and `filters`). Evidence entries use `source_id`, `paragraph_id`, and literal `quote`. A node’s scope is the paper ID for a specific object or `concept` for a shared general entity with evidence from every paper where it is queried. In the work file, filters are exact equality on any of `subject`, `predicate`, `object`, and `source_id`. Run at least three distinct useful queries, including cross-paper retrieval where supported. Do not treat a no-match as proof of absence.

```sh
python3 scripts/query_graph.py /app/work/graph.json --out /app/work/queries.json
```

Use the available Python command. The checker rejects unknown node references, wrong-source connections and mismatched quotes. Each executed query returns a subgraph of matching edges and their nodes with provenance. Read the extracted relations and merge ledger against the sources for scientific meaning and verify that both papers are represented. Fit the final result to the case’s original `output_contract`, including `case_id`, statuses and uncertainty. Save it as `/app/output/result.json` with required graph artifacts under `/app/output`. State any gap due to missing materials, lack of comparable conditions, unreadable notation, or an unmatched query.

### Illustrative example

Given separate paper records for two experiments mentioning the same polymer, give each experiment a paper-scoped sample node and attach the two excerpt references to the shared polymer concept. A query filtering by the first paper’s `source_id` and `predicate=uses` should return its assay-to-sample edge and quoted passage. An otherwise identical query for a paper with no such edge returns `no_match`.
