"""Extract source-positioned PDF line records with two-column reading order."""

import argparse
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
    return best[2] if best[0] >= 4 else None


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


def extract_page(page, layout, split):
    words = page.extract_words(use_text_flow=False, expand_ligatures=False, x_tolerance=1.7)
    bands = line_bands(words)
    if layout == "two" and words:
        boundary = page.bbox[0] + page.width * split
    elif layout == "auto" and words:
        boundary = infer_boundary(bands, page.width, page.bbox[0])
    else:
        boundary = None

    lines = []
    for number, (column, items) in enumerate(ordered_lines(bands, page.width, boundary), start=1):
        lines.append({
            "id": f"p{page.page_number}-l{number}",
            "region": column,
            "bbox": [round(value, 2) for value in (
                min(word["x0"] for word in items), min(word["top"] for word in items),
                max(word["x1"] for word in items), max(word["bottom"] for word in items),
            )],
            "text": " ".join(word["text"] for word in items),
        })

    warnings = []
    if not words:
        warnings.append("no selectable text was extracted")
    elif any(not word["upright"] for word in words):
        warnings.append("rotated text needs visual ordering review")
    if any("\ufffd" in line["text"] or "(cid:" in line["text"] for line in lines):
        warnings.append("unmapped characters need glyph inspection")
    return {
        "physical_page": page.page_number,
        "width": round(page.width, 2),
        "height": round(page.height, 2),
        "page_bbox": [round(value, 2) for value in page.bbox],
        "split_x": round(boundary, 2) if boundary is not None else None,
        "lines": lines,
        "warnings": warnings,
    }


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

    status = "ok"
    if not any(page["lines"] for page in pages):
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
