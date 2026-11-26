"""Index original paper passages and verify evidence citations with Python 3.9+."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET


HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
NUMBER = re.compile(r"[+\-−]?[0-9]+(?:[.,][0-9]+)*(?:[eE][+\-−]?[0-9]+)?[%‰]?")
EMBEDDED_JATS_BLOCKS = {"fig", "fig-group", "table-wrap", "boxed-text", "list", "disp-quote"}


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def number_tokens(text):
    compact_percent = re.sub(r"(?<=[0-9])\s+([%‰])", r"\1", text)
    return {token.replace("−", "-").lower() for token in NUMBER.findall(compact_percent)}


def text_blocks(text, markdown=False):
    headings = []
    lines = []
    start = 0
    for line_number, line in enumerate([*text.splitlines(), ""], start=1):
        heading = HEADING.match(line) if markdown else None
        if heading or not line.strip():
            if lines:
                yield {
                    "section": [title for _, title in headings],
                    "locator": f"lines {start}-{line_number - 1}",
                    "text": normalized("\n".join(lines)),
                }
                lines.clear()
            if heading:
                level = len(heading[1])
                headings = [(depth, title) for depth, title in headings if depth < level]
                headings.append((level, heading[2].strip()))
        else:
            if not lines:
                start = line_number
            lines.append(line)


def jats_blocks(path):
    root = ET.parse(path).getroot()
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    articles = [root] if root.tag == "article" else root.findall("./article")
    if len(articles) != 1:
        raise ValueError("expected one JATS article per XML source")
    article = articles[0]

    def visit(node, sections, locator):
        if node.tag == "sec":
            title = node.find("./title")
            heading = normalized("".join(title.itertext())) if title is not None else ""
            sections = [*sections, heading or node.get("id") or locator.rsplit("/", 1)[-1]]

        label = node.findtext("./label")
        if label and node.tag in {"fig", "table-wrap"}:
            locator = f"{locator} ({normalized(label)})"

        if node.tag in {"p", "caption", "table"}:
            if node.tag == "table":
                rendered = "\n".join(
                    " | ".join(normalized("".join(cell.itertext())) for cell in row)
                    for row in node.iter("tr")
                )
            else:
                parts = [node.text or ""]
                for child in node:
                    if child.tag not in EMBEDDED_JATS_BLOCKS:
                        parts.extend(child.itertext())
                    parts.append(child.tail or "")
                rendered = normalized("".join(parts))
            if rendered.strip():
                original_id = node.get("id")
                source_locator = f"JATS id={original_id} ({locator})" if original_id else f"JATS {locator}"
                yield {"section": sections, "locator": source_locator, "text": rendered}
            for ordinal, child in enumerate(node, start=1):
                if child.tag in EMBEDDED_JATS_BLOCKS:
                    yield from visit(child, sections, f"{locator}/{child.tag}[child {ordinal}]")
            return

        for ordinal, child in enumerate(node, start=1):
            if child.tag in EMBEDDED_JATS_BLOCKS or child.tag in {
                "sec", "p", "table", "caption", "list-item", "table-wrap-foot",
            }:
                yield from visit(child, sections, f"{locator}/{child.tag}[child {ordinal}]")

    for ordinal, abstract in enumerate(article.findall("./front/article-meta/abstract"), start=1):
        yield from visit(abstract, ["Abstract"], f"article-meta/abstract[{ordinal}]")
    body = article.find("./body")
    if body is not None:
        yield from visit(body, [], "body")


def pdf_blocks(path):
    binary = shutil.which("pdftotext")
    if binary is None:
        raise ValueError("pdftotext is unavailable. Render or OCR the PDF with the available tools.")
    completed = subprocess.run(
        [binary, "-enc", "UTF-8", str(path.resolve()), "-"],
        capture_output=True,
        check=True,
        timeout=120,
    )
    pages = completed.stdout.decode("utf-8").split("\f")
    if len(pages) > 1 and pages[-1] == "":
        pages.pop()
    passages = []
    blank_pages = []
    for page_number, page in enumerate(pages, start=1):
        blocks = list(text_blocks(page))
        if not blocks:
            blank_pages.append(page_number)
        for block in blocks:
            block["locator"] = f"physical PDF page {page_number}, extracted {block['locator']}"
            passages.append(block)
    warnings = []
    if blank_pages:
        warnings.append(f"Pages without extractable text: {blank_pages}")
    if completed.stderr.strip():
        warnings.append("pdftotext emitted warnings. Verify affected material in the source PDF.")
    return passages, warnings


def build_index(path, source_id):
    suffix = path.suffix.lower()
    warnings = []
    if suffix in {".xml", ".nxml"}:
        passages = list(jats_blocks(path))
    elif suffix in {".md", ".txt"}:
        passages = list(text_blocks(path.read_text(encoding="utf-8-sig"), markdown=suffix == ".md"))
    elif suffix == ".pdf":
        passages, warnings = pdf_blocks(path)
    else:
        raise ValueError("use JATS XML, Markdown, UTF-8 text, or a searchable PDF")
    if not passages:
        raise ValueError("no readable passages were extracted")
    for ordinal, passage in enumerate(passages, start=1):
        passage["id"] = f"p{ordinal:04d}"
    return {"source_id": source_id, "filename": path.name, "warnings": warnings, "passages": passages}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_evidence(entries, indexes):
    if not isinstance(entries, list) or not entries:
        raise ValueError("evidence JSON must be a nonempty list of claims")
    passages = {}
    source_ids = set()
    for index in indexes:
        source_id = index["source_id"]
        if source_id in source_ids:
            raise ValueError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        for item in index["passages"]:
            key = (source_id, item["id"])
            if key in passages:
                raise ValueError(f"duplicate anchor: {source_id}/{item['id']}")
            passages[key] = normalized(item["text"])

    failures = []
    seen_ids = set()
    valid_citations = 0
    for entry in entries:
        note_id = entry["id"]
        claim = entry["claim"]
        citations = entry["evidence"]
        if not isinstance(note_id, str) or not note_id.strip() or note_id in seen_ids:
            raise ValueError("claim ids must be nonempty unique strings")
        seen_ids.add(note_id)
        if not isinstance(claim, str) or not claim.strip() or not isinstance(citations, list) or not citations:
            failures.append(f"{note_id}: expected a nonempty claim and evidence list")
            continue
        quoted_numbers = set()
        for citation in citations:
            key = (citation["source_id"], citation["anchor_id"])
            quote = normalized(citation["quote"])
            if key not in passages:
                failures.append(f"{note_id}: unknown anchor {key[0]}/{key[1]}")
            elif not quote or quote not in passages[key]:
                failures.append(f"{note_id}: quote does not match {key[0]}/{key[1]}")
            else:
                valid_citations += 1
                quoted_numbers.update(number_tokens(quote))
        unverified = number_tokens(claim) - quoted_numbers
        if unverified:
            failures.append(f"{note_id}: numbers absent from matching quotes: {', '.join(sorted(unverified))}")
    return {
        "status": "fail" if failures else "pass",
        "claims": len(entries),
        "valid_citations": valid_citations,
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="extract passages with stable locators")
    index.add_argument("source", type=Path)
    index.add_argument("--source-id")
    index.add_argument("--out", type=Path, required=True)
    check = commands.add_parser("check", help="verify quoted evidence and numeric tokens")
    check.add_argument("evidence", type=Path)
    check.add_argument("indexes", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "index":
            if args.source.resolve() == args.out.resolve():
                raise ValueError("index output must differ from the source")
            result = build_index(args.source, args.source_id or args.source.name)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"passages": len(result["passages"]), "warnings": result["warnings"]}))
            return 0
        result = check_evidence(read_json(args.evidence), [read_json(path) for path in args.indexes])
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 1 if result["failures"] else 0
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError, subprocess.SubprocessError) as error:
        print(f"evidence: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
