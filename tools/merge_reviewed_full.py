#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Merge reviewed QA full contents into the original QA JSON by qa_id.

Inputs:
  1) reviewed_full.json  - a JSON that contains fully edited/approved QAs (must include qa_id),
                           can be structured as:
                             - { "segments": [ { ..., "qas": [ {qa_id, ...}, ... ] }, ... ] }
                             - { "<segment_id>": { ..., "qas": [ {qa_id, ...}, ... ] }, ... }
                             - { "qas": [ {qa_id, ...}, ... ] }
                             - [ {qa_id, ...}, ... ] (flat list)
  2) original_full.json  - your original, full-format candidate QA file to merge into
  3) output.json         - path to write the merged result (original structure preserved)

Behavior:
  - For each qa in the original file, if its qa_id is found in the reviewed file, the entire qa object
    is replaced by the reviewed one (qa_id preserved).
  - Adds/overwrites qa['reviewed'] = True for matched items. Unmatched items keep their original content.
  - The surrounding structure (segments, metadata, ordering) is preserved as in the original file.

Usage (PowerShell):
  python tools/merge_reviewed_full.py reviewed_full.json result/qacandidate_round_1.json result/qacandidate_round_1_merged.json
"""

import json
import os
import sys
from typing import Any, Dict, List, Tuple


def _iter_qas_from_data(data: Any) -> List[Dict[str, Any]]:
    """Extract a flat list of QA dicts from various supported data shapes."""
    qas: List[Dict[str, Any]] = []
    if isinstance(data, list):
        # flat list of QAs
        for item in data:
            if isinstance(item, dict) and 'qa_id' in item:
                qas.append(item)
        return qas

    if not isinstance(data, dict):
        return qas

    # {"segments": [ { qas: [...] }, ... ]}
    segs = data.get('segments')
    if isinstance(segs, list):
        for seg in segs:
            if isinstance(seg, dict) and isinstance(seg.get('qas'), list):
                for qa in seg['qas']:
                    if isinstance(qa, dict) and 'qa_id' in qa:
                        qas.append(qa)

    # {"qas": [ ... ]}
    if isinstance(data.get('qas'), list):
        for qa in data['qas']:
            if isinstance(qa, dict) and 'qa_id' in qa:
                qas.append(qa)

    # { segment_id: { qas: [...] }, ... }
    for key, val in data.items():
        if key in ('segments', 'qas'):
            continue
        if isinstance(val, dict) and isinstance(val.get('qas'), list):
            for qa in val['qas']:
                if isinstance(qa, dict) and 'qa_id' in qa:
                    qas.append(qa)

    return qas


def _replace_qas_in_place(original: Any, qa_map: Dict[str, Dict[str, Any]]) -> Tuple[Any, int]:
    """Replace qas in the original structure with ones from qa_map where qa_id matches.
    Returns (modified_original, replaced_count).
    """
    replaced = 0

    def process_qas_list(qas_list: List[Dict[str, Any]]):
        nonlocal replaced
        for i, qa in enumerate(qas_list):
            if not isinstance(qa, dict):
                continue
            qa_id = qa.get('qa_id')
            if not isinstance(qa_id, str):
                continue
            reviewed_qa = qa_map.get(qa_id)
            if reviewed_qa:
                # Make a copy and ensure reviewed flag
                new_obj = dict(reviewed_qa)
                new_obj['qa_id'] = qa_id
                new_obj['reviewed'] = True
                qas_list[i] = new_obj
                replaced += 1

    if isinstance(original, list):
        process_qas_list(original)
        return original, replaced

    if not isinstance(original, dict):
        return original, replaced

    # segments list
    segs = original.get('segments')
    if isinstance(segs, list):
        for seg in segs:
            if isinstance(seg, dict) and isinstance(seg.get('qas'), list):
                process_qas_list(seg['qas'])

    # top-level qas list
    if isinstance(original.get('qas'), list):
        process_qas_list(original['qas'])

    # mapping by segment id
    for key, val in original.items():
        if key in ('segments', 'qas'):
            continue
        if isinstance(val, dict) and isinstance(val.get('qas'), list):
            process_qas_list(val['qas'])

    return original, replaced


def main(argv: List[str]) -> None:
    if len(argv) != 4:
        print(
            'Usage: python tools/merge_reviewed_full.py <reviewed_full.json> <original_full.json> <output.json>',
            file=sys.stderr,
        )
        raise SystemExit(2)

    reviewed_path = argv[1]
    original_path = argv[2]
    output_path = argv[3]

    if not os.path.exists(reviewed_path):
        raise SystemExit(f'Reviewed JSON not found: {reviewed_path}')
    if not os.path.exists(original_path):
        raise SystemExit(f'Original JSON not found: {original_path}')

    with open(reviewed_path, 'r', encoding='utf-8') as f:
        reviewed_data = json.load(f)
    with open(original_path, 'r', encoding='utf-8') as f:
        original_data = json.load(f)

    reviewed_qas = _iter_qas_from_data(reviewed_data)
    qa_map: Dict[str, Dict[str, Any]] = {}
    for qa in reviewed_qas:
        qa_id = qa.get('qa_id')
        if isinstance(qa_id, str):
            qa_map[qa_id] = qa

    merged, replaced = _replace_qas_in_place(original_data, qa_map)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f'Merged {replaced} reviewed QAs into original. Wrote: {output_path}')


if __name__ == '__main__':
    main(sys.argv)


