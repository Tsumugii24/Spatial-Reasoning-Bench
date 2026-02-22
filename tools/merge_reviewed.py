#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
from typing import Any, Dict, List, Set


def load_selected_qa_ids(selection_json_path: str) -> Set[str]:
    """Load selected QA ids from a backup JSON.
    Supports two formats:
      1) { "selectedQAs": ["segA_qa_0", ...], ... }
      2) ["segA_qa_0", ...]
    """
    with open(selection_json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid selection JSON: {e}")

    if isinstance(data, list):
        return set(x for x in data if isinstance(x, str))

    if isinstance(data, dict):
        selected = data.get('selectedQAs', [])
        if isinstance(selected, list):
            return set(x for x in selected if isinstance(x, str))

    raise SystemExit("Could not parse selectedQAs from selection JSON.")


def merge_reviewed_flags(selected_ids: Set[str], input_json_path: str, output_json_path: str) -> int:
    """Merge reviewed flag into a copy of input JSON and write to output.
    Returns number of QAs processed.
    Expected candidate QA JSON structure:
      {
        "<segment_id>": { "qas": [ { "qa_id": "<segment_id>_qa_<index>", ... }, ... ] },
        ...
      }
    Also tolerates top-level {"segments": [...] } or top-level {"qas": [...]}.
    """
    if not os.path.exists(input_json_path):
        raise SystemExit(f"Input JSON not found: {input_json_path}")

    with open(input_json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid input JSON: {e}")

    if not isinstance(data, dict):
        raise SystemExit("Input JSON root must be an object (dict).")

    updated = 0

    def process_qas(qas: List[Dict[str, Any]]) -> int:
        count = 0
        for qa in qas:
            if not isinstance(qa, dict):
                continue
            qa_id = qa.get('qa_id')
            if not isinstance(qa_id, str):
                continue
            qa['reviewed'] = qa_id in selected_ids
            count += 1
        return count

    # Common mapping structure: { segment_id: { qas: [...] } }
    for seg_id, seg in (data.items() if isinstance(data, dict) else []):
        if not isinstance(seg, dict):
            continue
        qas = seg.get('qas')
        if isinstance(qas, list):
            updated += process_qas(qas)

    # If there is a top-level 'segments' list
    if isinstance(data.get('segments'), list):
        for seg in data['segments']:
            if not isinstance(seg, dict):
                continue
            qas = seg.get('qas')
            if isinstance(qas, list):
                updated += process_qas(qas)

    # If there is a top-level 'qas' list
    if isinstance(data.get('qas'), list):
        updated += process_qas(data['qas'])

    os.makedirs(os.path.dirname(output_json_path) or '.', exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return updated


def write_reviewed_only(selected_ids: Set[str], input_json_path: str, reviewed_only_output: str) -> int:
    """Create a reviewed-only JSON file that contains the full updated QA contents
    for those whose qa_id is in selected_ids. Keeps segment grouping when possible.
    Returns number of reviewed QAs written.
    """
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    reviewed_count = 0

    # Prepare output in the same structural shape, but with qas filtered to reviewed only
    def filter_qas(qas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        nonlocal reviewed_count
        result: List[Dict[str, Any]] = []
        for qa in qas:
            if not isinstance(qa, dict):
                continue
            qa_id = qa.get('qa_id')
            if isinstance(qa_id, str) and qa_id in selected_ids:
                qa_copy = dict(qa)
                qa_copy['reviewed'] = True
                result.append(qa_copy)
                reviewed_count += 1
        return result

    reviewed_output: Any

    if isinstance(data, dict) and 'segments' in data and isinstance(data['segments'], list):
        reviewed_output = {'segments': []}
        for seg in data['segments']:
            if not isinstance(seg, dict):
                continue
            seg_copy = {k: v for k, v in seg.items() if k != 'qas'}
            qas = seg.get('qas') if isinstance(seg.get('qas'), list) else []
            seg_copy['qas'] = filter_qas(qas)
            reviewed_output['segments'].append(seg_copy)
    elif isinstance(data, dict) and isinstance(data.get('qas'), list):
        reviewed_output = {'qas': filter_qas(data['qas'])}
    elif isinstance(data, dict):
        # mapping by segment_id
        reviewed_output = {}
        for seg_id, seg in data.items():
            if not isinstance(seg, dict):
                continue
            seg_copy = {k: v for k, v in seg.items() if k != 'qas'}
            qas = seg.get('qas') if isinstance(seg.get('qas'), list) else []
            seg_copy['qas'] = filter_qas(qas)
            reviewed_output[seg_id] = seg_copy
    else:
        reviewed_output = []

    os.makedirs(os.path.dirname(reviewed_only_output) or '.', exist_ok=True)
    with open(reviewed_only_output, 'w', encoding='utf-8') as f:
        json.dump(reviewed_output, f, ensure_ascii=False, indent=2)

    return reviewed_count


def main(argv: List[str]) -> None:
    if not (4 <= len(argv) <= 5):
        print(
            "Usage: python tools/merge_reviewed.py <qa_selection_state.json> <input.json> <output.json> [reviewed_only_output.json]",
            file=sys.stderr,
        )
        raise SystemExit(2)

    selection_path = argv[1]
    input_path = argv[2]
    output_path = argv[3]
    reviewed_only_output = argv[4] if len(argv) == 5 else None

    selected_ids = load_selected_qa_ids(selection_path)
    updated = merge_reviewed_flags(selected_ids, input_path, output_path)
    print(f"Merged reviewed flags into {updated} QAs. Wrote: {output_path}")

    if reviewed_only_output:
        reviewed_count = write_reviewed_only(selected_ids, input_path, reviewed_only_output)
        print(f"Exported {reviewed_count} reviewed QAs with full content to: {reviewed_only_output}")


if __name__ == '__main__':
    main(sys.argv)


