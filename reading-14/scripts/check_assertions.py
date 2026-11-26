"""Check a ledger of atomic assertions against exact source passages."""

import argparse
import json
from pathlib import Path
import unicodedata


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected nonempty text")
    return " ".join(unicodedata.normalize("NFC", value).split())


def check(ledger):
    sources = {}
    for source in ledger["sources"]:
        source_id = text(source["id"])
        if source_id in sources:
            raise ValueError(f"duplicate source ID: {source_id}")
        text(source["title"])
        sources[source_id] = {key: text(value) for key, value in source["passages"].items()}
    if not sources or not ledger["assertions"]:
        raise ValueError("provide sources and at least one assertion")

    ids = set()
    signatures = set()
    issues = []
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
            elif quote not in passage:
                issues.append({"id": claim_id, "kind": "quote_mismatch", "source_id": source_id, "locator": locator})
            else:
                checked_quotes += 1
    return {"assertions": len(ids), "checked_quotes": checked_quotes, "issues": issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    try:
        result = check(json.loads(args.ledger.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return bool(result["issues"])


if __name__ == "__main__":
    raise SystemExit(main())
