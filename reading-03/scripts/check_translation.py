"""Check a scientific translation alignment ledger."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata


NUMBERS = re.compile(r"(?:(?:<=|>=|[<>≤≥])\s*)?[+−-]?[0-9]+(?:[.,][0-9]+)*(?:[eE][+−-]?[0-9]+)?(?:\s*[%‰])?")


def normalized(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("a nonempty text field was expected")
    return " ".join(unicodedata.normalize("NFC", text).split())


def numbers(text):
    return Counter(token.replace("≤", "<=").replace("≥", ">=").replace("−", "-").replace(" ", "").lower() for token in NUMBERS.findall(text))


MEASUREMENT = re.compile(
    r"(?<![A-Za-z0-9_.])([+−-]?\d+(?:[.,]\d+)*(?:[eE][+−-]?\d+)?)\s*"
    r"(µg|μg|mg|kg|g|µL|μL|mL|L|µm|μm|nm|mm|cm|km|m|mV|V|kPa|MPa|Pa|°C)(?![A-Za-z])"
)


def measurements(passage):
    return Counter((value.replace("−", "-"), unit.replace("μ", "µ"))
                   for value, unit in MEASUREMENT.findall(passage))


def ordered_ids(rows):
    ids = [normalized(row["id"]) for row in rows]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("passage IDs must be present and unique")
    return ids


def check(ledger):
    source = ledger["segments"]
    target = ledger["translations"]
    source_ids = ordered_ids(source)
    if source_ids != ordered_ids(target):
        return {"checked": 0, "issues": [{"kind": "passage_order_or_coverage"}]}
    glossary = [(normalized(term["source"]), normalized(term["target"])) for term in ledger.get("glossary", [])]
    issues = []
    for passage_id, original, translated in zip(source_ids, source, target):
        text = normalized(original["source"])
        translation = normalized(translated["target"])
        missing = measurements(text) - measurements(translation)
        for (value, unit), count in missing.items():
            issues.append({"id": passage_id, "kind": "measurement_needs_review",
                           "text": f"{value} {unit}", "count": count})
        for token, difference in (numbers(text) - numbers(translation)).items():
            issues.append({"id": passage_id, "kind": "missing_number", "text": token, "count": difference})
        for token, difference in (numbers(translation) - numbers(text)).items():
            issues.append({"id": passage_id, "kind": "added_number", "text": token, "count": difference})
        for token in map(normalized, original.get("protected", [])):
            if not text.count(token) or text.count(token) != translation.count(token):
                issues.append({"id": passage_id, "kind": "protected_token", "text": token})
        for term_source, term_target in glossary:
            pattern = rf"(?<![A-Za-z0-9]){re.escape(term_source)}(?![A-Za-z0-9])"
            if len(re.findall(pattern, text, re.IGNORECASE)) > translation.count(term_target):
                issues.append({"id": passage_id, "kind": "glossary_drift", "text": term_source})
    return {"checked": len(source), "issues": issues}


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
