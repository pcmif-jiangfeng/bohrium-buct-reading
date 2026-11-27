"""Check a ledger of atomic assertions against exact source passages."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected nonempty text")
    return " ".join(unicodedata.normalize("NFC", value).split())


def contains_quote(passage, quote):
    left = r"(?<![A-Za-z0-9_])" if re.match(r"[A-Za-z0-9_]", quote) else ""
    right = r"(?![A-Za-z0-9_])" if re.search(r"[A-Za-z0-9_]$", quote) else ""
    if quote[0].isascii() and quote[0].isdigit():
        left += r"(?<![0-9][.,])(?<![+−-])"
    if quote[-1].isascii() and quote[-1].isdigit():
        right += r"(?![.,][0-9])"
    return re.search(left + re.escape(quote) + right, passage) is not None


def table_cell(wrapper, coordinates):
    if wrapper is None or wrapper.tag.rsplit("}", 1)[-1] != "table-wrap":
        raise ValueError("table ID must name one JATS table-wrap")
    if not isinstance(coordinates, list) or len(coordinates) != 2 or not all(
        type(value) is int and value >= 1 for value in coordinates
    ):
        raise ValueError("cell requires one-based row and cell positions")
    tables = wrapper.findall(".//{*}table")
    if len(tables) != 1:
        raise ValueError("expected one XML table in wrapper")
    rows = tables[0].findall(".//{*}tr")
    row, column = coordinates
    cells = [el for el in rows[row - 1] if el.tag.rsplit("}", 1)[-1] in {"td", "th"}] if row <= len(rows) else []
    if column > len(cells):
        raise ValueError("cell is outside the selected table")
    return "".join(cells[column - 1].itertext())


def file_passages(root, source, issues):
    source_id = text(source["id"])
    filename = source["path"]
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("expected a relative source file path")
    relative = Path(filename)
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root):
        raise ValueError("source path escapes its root")
    data = path.read_bytes()
    anchors = source["passages"]
    if not isinstance(anchors, dict) or not anchors:
        raise ValueError("provide a nonempty map of source selectors")
    locator_keys = [text(key) for key in anchors]
    if len(set(locator_keys)) != len(locator_keys):
        raise ValueError("duplicate locator after normalization")
    lines, nodes = None, {}
    document = None
    if any(isinstance(selector, dict) and ("jats_id" in selector or "table_id" in selector) for selector in anchors.values()):
        for element in ET.fromstring(data).iter():
            identifier = element.get("id") or element.get("{http://www.w3.org/XML/1998/namespace}id")
            if identifier:
                nodes[identifier] = None if identifier in nodes else element
    passages = {}
    for locator, selector in zip(locator_keys, anchors.values()):
        try:
            if isinstance(selector, dict) and set(selector) == {"jats_id"}:
                node = nodes.get(text(selector["jats_id"]))
                if node is None or node.tag.rsplit("}", 1)[-1] not in {"p", "td", "th", "caption"}:
                    raise ValueError("JATS ID must name one unambiguous paragraph, cell, or caption")
                passage = "".join(node.itertext())
            elif isinstance(selector, dict) and set(selector) == {"table_id", "cell"}:
                passage = table_cell(nodes.get(text(selector["table_id"])), selector["cell"])
            elif isinstance(selector, dict) and set(selector) == {"json_pointer"}:
                if document is None:
                    document = json.loads(data)
                pointer = selector["json_pointer"]
                if not isinstance(pointer, str) or not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
                    raise ValueError("invalid JSON pointer")
                passage = document
                for component in pointer[1:].split("/"):
                    key = component.replace("~1", "/").replace("~0", "~")
                    if isinstance(passage, dict) and key in passage:
                        passage = passage[key]
                    elif isinstance(passage, list) and re.fullmatch(r"0|[1-9][0-9]*", key) and int(key) < len(passage):
                        passage = passage[int(key)]
                    else:
                        raise ValueError("JSON pointer does not resolve")
            elif isinstance(selector, dict) and set(selector) == {"lines"}:
                if lines is None:
                    lines = data.decode("utf-8-sig").splitlines()
                span = selector["lines"]
                if not isinstance(span, list) or len(span) != 2 or not all(type(value) is int for value in span):
                    raise ValueError("line range must contain two integer line numbers")
                start, end = span
                if not 1 <= start <= end <= len(lines):
                    raise ValueError("line range is outside the source")
                passage = "\n".join(lines[start - 1:end])
            else:
                raise ValueError("expected jats_id, json_pointer, or inclusive lines")
            passages[locator] = text(passage)
        except ValueError as error:
            issues.append({"kind": "invalid_source_anchor", "source_id": source_id, "locator": locator, "reason": str(error)})
    return passages, {"source_id": source_id, "path": relative.as_posix(), "sha256": hashlib.sha256(data).hexdigest()}


def check(ledger, source_root=None):
    sources = {}
    issues, source_files = [], []
    if source_root is not None:
        source_root = source_root.resolve(strict=True)
        if not source_root.is_dir():
            raise ValueError("source root must be a directory")
    for source in ledger["sources"]:
        source_id = text(source["id"])
        if source_id in sources:
            raise ValueError(f"duplicate source ID: {source_id}")
        text(source["title"])
        if source_root is None:
            sources[source_id] = {key: text(value) for key, value in source["passages"].items()}
            continue
        try:
            sources[source_id], record = file_passages(source_root, source, issues)
            source_files.append(record)
        except (OSError, ValueError, RuntimeError, KeyError, ET.ParseError) as error:
            sources[source_id] = {}
            reason = error.strerror if isinstance(error, OSError) else str(error)
            issues.append({"kind": "source_unavailable", "source_id": source_id, "reason": reason})
    if not sources or not ledger["assertions"]:
        raise ValueError("provide sources and at least one assertion")

    ids = set()
    signatures = set()
    checked_quotes = 0
    for claim in ledger["assertions"]:
        claim_id = text(claim["id"])
        if claim_id in ids:
            raise ValueError(f"duplicate assertion ID: {claim_id}")
        ids.add(claim_id)
        triple = tuple(text(claim[key]) for key in ("subject", "predicate", "object"))
        scope = text(claim["scope"]) if claim.get("scope") else ""
        references = claim["evidence"]
        source_ids = tuple(sorted({text(entry["source_id"]) for entry in references}))
        signature = (*triple, scope, source_ids)
        if signature in signatures:
            issues.append({"id": claim_id, "kind": "duplicate_assertion"})
        signatures.add(signature)
        if not references:
            issues.append({"id": claim_id, "kind": "missing_evidence"})
        for item in references:
            source_id = text(item["source_id"])
            locator = text(item["locator"])
            quote = text(item["quote"])
            passage = sources.get(source_id, {}).get(locator)
            if passage is None:
                issues.append({"id": claim_id, "kind": "unresolved_locator", "source_id": source_id, "locator": locator})
            elif not contains_quote(passage, quote):
                issues.append({"id": claim_id, "kind": "quote_mismatch", "source_id": source_id, "locator": locator})
            else:
                checked_quotes += 1
    result = {"assertions": len(ids), "checked_quotes": checked_quotes, "issues": issues}
    if source_root is not None:
        result["source_files"] = source_files
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--source-root", type=Path, help="verify selectors against files under this directory")
    args = parser.parse_args()
    try:
        result = check(json.loads(args.ledger.read_text(encoding="utf-8-sig")), args.source_root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return bool(result["issues"])


if __name__ == "__main__":
    raise SystemExit(main())
