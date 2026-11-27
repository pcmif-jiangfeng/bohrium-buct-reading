"""Extract source-positioned PDF line records with two-column reading order."""

import argparse
from bisect import bisect_right
from itertools import groupby
import json
from pathlib import Path
import sys


GUTTER_FRACTION = 0.012


def line_bands(words, tolerance=2.5):
    bands = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not bands or word["top"] - bands[-1][0]["top"] > tolerance:
            bands.append([])
        bands[-1].append(word)
    return [sorted(band, key=lambda item: item["x0"]) for band in bands]


def split_band(words, boundary, minimum_gap):
    left = [word for word in words if word["x1"] <= boundary]
    right = [word for word in words if word["x0"] >= boundary]
    if len(left) + len(right) != len(words):
        return None
    if left and right and min(word["x0"] for word in right) - max(word["x1"] for word in left) < minimum_gap:
        return None
    return left, right


def infer_boundary(bands, width, left_edge):
    half = left_edge + width / 2
    margin = width * GUTTER_FRACTION
    best = (0, 0.0, half)
    for tick in range(42, 59):
        boundary = left_edge + width * tick / 100
        hits = 0
        for band in bands:
            columns = split_band(band, boundary, margin)
            if columns is not None and all(len(column) >= 2 for column in columns):
                hits += 1
        best = max(best, (hits, -abs(boundary - half), boundary))
    if best[0] >= 4:
        return best[2]

    # Staggered columns may never share a baseline. Require tracks of long,
    # similarly aligned lines on both sides over the same vertical interval.
    candidates = []
    for tick in range(42, 59):
        boundary = left_edge + width * tick / 100
        tracks = ([], [])
        for band in bands:
            if len(band) < 3 or band[-1]["x1"] - band[0]["x0"] < width * 0.12:
                continue
            if band[-1]["x1"] <= boundary - margin / 2:
                tracks[0].append(band[0])
            elif band[0]["x0"] >= boundary + margin / 2:
                tracks[1].append(band[0])
        if min(map(len, tracks)) < 4:
            continue
        top = max(track[0]["top"] for track in tracks)
        bottom = min(track[-1]["top"] for track in tracks)
        counts = []
        for track in tracks:
            starts = sorted(word["x0"] for word in track if top <= word["top"] <= bottom)
            counts.append(max((sum(0 <= x - start <= margin * 2 for x in starts) for start in starts), default=0))
        if min(counts) >= 3:
            candidates.append((min(counts), -abs(boundary - half), boundary))
    return max(candidates)[2] if candidates else None


def ordered_lines(bands, width, boundary):
    if boundary is None:
        yield from (("single", band) for band in bands)
        return

    left_lines, right_lines = [], []
    for band in bands:
        columns = split_band(band, boundary, width * GUTTER_FRACTION)
        if columns is None:
            yield from (("left", line) for line in left_lines)
            yield from (("right", line) for line in right_lines)
            left_lines.clear()
            right_lines.clear()
            yield "span", band
            continue
        left, right = columns
        if left:
            left_lines.append(left)
        if right:
            right_lines.append(right)
    yield from (("left", line) for line in left_lines)
    yield from (("right", line) for line in right_lines)


def rounded_box(box):
    return [round(value, 2) for value in box]


def ruled_tables(page):
    for table in sorted(page.find_tables(), key=lambda item: (item.bbox[1], item.bbox[0])):
        values = table.extract(x_tolerance=1.7)
        # Two populated rows distinguish a data grid from most frames and artwork.
        if sum(sum(bool(text and text.strip()) for text in row) >= 2 for row in values) < 2:
            continue
        rows = [[None if box is None else {"text": text or "", "bbox": rounded_box(box)}
                 for box, text in zip(row.cells, texts)] for row, texts in zip(table.rows, values)]
        yield table.cells, {"bbox": rounded_box(table.bbox), "rows": rows}


def inside_cell(word, cells):
    x = (word["x0"] + word["x1"]) / 2
    y = (word["top"] + word["bottom"]) / 2
    return any(left <= x < right and top <= y < bottom for left, top, right, bottom in cells)


def extract_page(page, layout, split):
    all_words = page.extract_words(use_text_flow=False, expand_ligatures=False, x_tolerance=1.7)
    tables, cells = [], []
    if all_words:
        for boxes, table in ruled_tables(page):
            tables.append({"id": f"p{page.page_number}-t{len(tables) + 1}", **table})
            cells.extend(boxes)
    words = [word for word in all_words if not inside_cell(word, cells)] if cells else all_words
    bands = line_bands(words)
    if layout == "two" and words:
        boundary = page.bbox[0] + page.width * split
    elif layout == "auto" and words:
        boundary = infer_boundary(bands, page.width, page.bbox[0])
    else:
        boundary = None

    # A spanning table remains a reading-order break after its text is moved to cells.
    cuts = sorted(table["bbox"][1] for table in tables
                  if boundary is not None and table["bbox"][0] < boundary < table["bbox"][2])
    regions = groupby(bands, key=lambda band: bisect_right(cuts, band[0]["top"]))
    ordered = (line for _, region in regions for line in ordered_lines(region, page.width, boundary))
    lines = []
    for number, (column, items) in enumerate(ordered, start=1):
        lines.append({
            "id": f"p{page.page_number}-l{number}",
            "region": column,
            "bbox": rounded_box((
                min(word["x0"] for word in items), min(word["top"] for word in items),
                max(word["x1"] for word in items), max(word["bottom"] for word in items),
            )),
            "text": " ".join(word["text"] for word in items),
        })

    warnings = []
    if not all_words:
        warnings.append("no selectable text was extracted")
    elif any(not word["upright"] for word in all_words):
        warnings.append("rotated text needs visual ordering review")
    if any("\ufffd" in word["text"] or "(cid:" in word["text"] for word in all_words):
        warnings.append("unmapped characters need glyph inspection")
    return {
        "physical_page": page.page_number,
        "image_regions": [
            {"id": f"p{page.page_number}-img{index}",
             "bbox": rounded_box(image[key] for key in ("x0", "top", "x1", "bottom"))}
            for index, image in enumerate(page.images, start=1)
        ],
        "width": round(page.width, 2),
        "height": round(page.height, 2),
        "page_bbox": [round(value, 2) for value in page.bbox],
        "split_x": round(boundary, 2) if boundary is not None else None,
        "lines": lines,
        "tables": tables,
        "warnings": warnings,
    }


def mark_recurring_margins(pages):
    groups = {}
    for page in pages:
        top, bottom = page["page_bbox"][1::2]
        band = (bottom - top) * 0.08
        for line in page["lines"]:
            y0, y1 = line["bbox"][1::2]
            side = "header" if y1 <= top + band else "footer" if y0 >= bottom - band else None
            if side:
                key = (side, line["text"], round((y0 - top) / (bottom - top), 2))
                groups.setdefault(key, []).append((page["physical_page"], line))
    for (side, _, _), occurrences in groups.items():
        if len({page for page, _ in occurrences}) >= 2:
            for _, line in occurrences:
                line["margin_candidate"] = side


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--layout", choices=("auto", "single", "two"), default="auto")
    parser.add_argument("--split", type=float, default=0.5)
    args = parser.parse_args()
    if not 0.2 < args.split < 0.8 or args.pdf.resolve() == args.out.resolve():
        parser.error("split must be between 0.2 and 0.8 and output must differ from source")

    try:
        import pdfplumber
    except ImportError:
        print("extract_layout: pdfplumber 0.11+ is required", file=sys.stderr)
        return 2

    try:
        with pdfplumber.open(args.pdf) as pdf:
            pages = [extract_page(page, args.layout, args.split) for page in pdf.pages]
    except (OSError, ValueError, pdfplumber.utils.exceptions.PdfminerException) as error:
        print(f"extract_layout: {error}", file=sys.stderr)
        return 2

    mark_recurring_margins(pages)
    status = "ok"
    if not any(page["lines"] or page["tables"] for page in pages):
        status = "no_selectable_text"
    elif any(page["warnings"] for page in pages):
        status = "needs_review"
    result = {"source": args.pdf.name, "coordinate_system": "pdfplumber page with y increasing down", "status": status, "pages": pages}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "pages": len(pages), "lines": sum(len(page["lines"]) for page in pages)}))
    return 1 if status == "no_selectable_text" else 0


if __name__ == "__main__":
    sys.exit(main())
