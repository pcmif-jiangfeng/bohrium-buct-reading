---
name: auditable-pdf-reading-order
description: Extract and audit the reading order of scientific PDFs with selectable text. Use for two-column scientific layouts, page-anchored text extraction, and review of ambiguous regions, formulas, figures, or tables in the source PDF.
---

# Auditable scientific PDF parsing

## Establish the source and output

In Harbor read `/input/case.json`, `task.md`, and the actual PDF. Use the supplied `case_id`, page range and exact `output_contract`. Check `environment/resources.yaml` if present to identify the available PDF extraction, rendering, and OCR tools. Source pages are physical, one-based PDF pages. Keep printed page labels distinct from physical pages.

## Extract and verify reading order

Run the included [layout extractor](scripts/extract_layout.py) with Python 3.9+ and `pdfplumber` 0.11+. Use the pinned version in the execution image where available. This script groups words into visual line bands, finds a repeated center gutter, emits left then right within each vertical region, and preserves the coordinates and text of each result line. Lines spanning the gutter delimit vertical regions. Explicitly select `--layout single` or `--layout two` only after checking the page image. With `--layout two`, `--split` sets the column boundary as a fraction of page width when a known asymmetric template needs it.

```sh
python3 /skills/weekly-skill/scripts/extract_layout.py /input/paper.pdf --out /app/work/layout.json
```

Inspect representative rendered pages and every flagged or ambiguous region. Verify the header and footer, column transitions, and reading order around figures, tables, section titles, and footnotes. Check the first and last line emitted for each column against the image. Preserve source spelling, punctuation, and symbols. Reconnect wrapped lines only when the original paragraph visibly continues. For a rotated page, overlapping or staggered text, a figure with embedded labels, or a complex table, isolate the region and inspect it directly. The line extractor does not infer merged cells, mathematical notation, or semantics. Keep text from such areas in separately identified structural records when the case requests them.

For a page without a text layer, follow the case's OCR policy and use the supplied renderer or OCR engine if available. Check OCR text against the page image and label the extraction method. Record password, unreadable image, absent content, and uncertain ordering as distinct reasons. Preserve successfully recovered pages if another page is unavailable. If the helper or its dependency is unavailable, use the pinned extraction tool and record its actual output and limitations.

## Deliver

Use the source pages and verified blocks to fill the case's requested structure and record uncertainties. Preserve exact snippets, source file identity, physical page, and bounding box for key results. Use page, region and original label when coordinates are not available. Store work files in `/app/work` and final files, including `/app/output/result.json`, under `/app/output`. Retain the case identifier, requested documents, schema fields and honest execution status. Separate verified text from areas requiring manual review.

## Minimal illustrative example

For an invented PDF page containing `Introduction` and `Methods` on the left and `Results` and `Discussion` on the right, verify the two-column layout and run with `--layout two`. The expected illustrative order is `Introduction`, `Methods`, `Results`, `Discussion`, with four line records and physical page 1. Coordinates and ordering for a real result must come from the actual case PDF.
