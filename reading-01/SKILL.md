---
name: auditable-pdf-reading-order
description: Parse scientific PDFs into source-anchored text and ruled table cells. Use for staggered or aligned reading columns, table row and column extraction, and visual review of figures, formulas, or scanned pages.
---

# Auditable scientific PDF parsing

## Establish the source and output

In Harbor read `/input/case.json`, `task.md`, and the actual PDF named by the case. List each required field or deliverable with its page scope. Check `environment/resources.yaml` if present for extraction, rendering, and OCR tools. Use physical, one-based page numbers for evidence and keep printed page labels separately when requested.

## Extract and verify reading order

Run the included [layout extractor](scripts/extract_layout.py) with Python 3.9+ and `pdfplumber` 0.11+. It detects a repeated center gutter from lines with shared baselines, or from aligned blocks that overlap vertically when the baselines differ. Spanning lines and tables separate the adjacent column regions. Apply `--layout single` or `--layout two` after checking the page image if a document-wide override is appropriate. With `--layout two`, `--split` sets the horizontal fraction for an asymmetric template.

```sh
python3 /skills/weekly-skill/scripts/extract_layout.py /input/paper.pdf --out /app/work/layout.json
```

The intermediate JSON uses `[x0, top, x1, bottom]` in PDF points. Each page has `lines` (`id`, `region`, `bbox`, `text`) and `tables` (`id`, `bbox`, `rows`). `rows` retains the physical cell grid: an empty cell has `text: ""` and its own coordinates, while a `null` slot has no independent cell box. Text inside the detected cell boxes lives in the table rather than in `lines`. Place each table back in the requested output near its verified caption, using the table and caption boxes as separate anchors. For an unruled or image-based table, inspect the rendered region and verify row and column assignments against visible labels. Keep a genuine empty cell distinct from unreadable or absent source content. Confirm merged cells and continuation pages visually.

A line with `margin_candidate` repeats at a similar height in the outer 8% of at least two physical pages. Compare it with the page image before moving it from the body into header/footer metadata. Preserve its original ID and coordinates. Unique footnotes, changing page labels and recurring table heads require separate inspection.

Render the pages in scope and check column transitions, figure boundaries, table and figure captions, section headings, footnotes, and repeated page furniture. Check the first and last line in each column against the image. Join wrapped lines only where the original paragraph continues. Keep title, authors, abstract, section hierarchy and references as separate records when requested. Transcribe visible formula symbols and preserve the printed equation label and page region. Mark unresolved glyphs or reading order at their source location.

For a page without a text layer, follow the case's OCR policy and use the supplied renderer or OCR engine if available. Check OCR text against the page image and label the extraction method. Record password, unreadable image, absent content, and uncertain ordering as distinct reasons. Preserve successfully recovered pages if another page is unavailable. If the helper or its dependency is unavailable, use the pinned extraction tool and record its actual output and limitations.

## Deliver

Write verified content early and finish the requested structure from the original pages, line records and tables. Use the exact `output_contract` field names and the original `case_id` in `/app/output/result.json`. For key items keep the source file, physical page, exact snippet and box or original label. For table rows include a row and column index in addition to page and cell location. Save intermediate files in `/app/work` and requested editable artifacts in `/app/output`. Before delivery, reopen `result.json`, confirm every required key and referenced file, and record the precise page or field for each missing, unreadable or ambiguous item.

## Minimal illustrative example

For an invented two-column PDF with several lines under each heading, run the default command and inspect page 1. The expected illustrative sequence is the left column's `Introduction` and `Methods`, then the right column's `Results` and `Discussion`. On a separate page with a ruled grid, a cell reading `12.5` appears in `tables[0].rows` with its own box. Use the actual case PDF to verify each record.

When pdfplumber is missing, the same command can use pypdf (tested with 6.x) to recover selectable text by physical page. A report with method pypdf_page_text contains page_text and warnings for each page. Use those pages for partial evidence and check columns, symbols and tables visually. A blank page record identifies where OCR may be needed.
