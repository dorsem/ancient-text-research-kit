#!/usr/bin/env python3
"""Reproduce a conditional arithmetic audit of the linked CDLI edition.

This computes with edited signs, including damaged counts. It does not infer
ancient units, accounting scope, recipients, or repairs to the inscription.
Run from any directory; --check compares with the committed result.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'corpus' / 'Uruk_P000928' / 'transliteration.atf'
RESULT = ROOT / 'uruk_arithmetic_result.json'


def audit(text):
    entries = []
    surface = column = None
    for line in text.splitlines():
        if line in ('@obverse', '@reverse'):
            surface = line[1:]
        elif line.startswith('@column '):
            column = int(line.split()[1])
        elif re.match(r'^\d+\. ', line):
            number, body = line.split('. ', 1)
            numeric, signs = body.split(' , ', 1)
            quantities = {}
            for token in numeric.split():
                m = re.fullmatch(r'(\d+)\((N01|N14)\)(#?)', token)
                if not m:
                    raise ValueError('Unsupported numeric notation: ' + token)
                if m[2] in quantities:
                    raise ValueError('Repeated numeric type: ' + token)
                quantities[m[2]] = int(m[1])
            entries.append(dict(locator=f'{surface}.{column}.{number}',
                                numeric=quantities, damaged_number='#' in numeric,
                                signs=signs))
    obverse = [e for e in entries if e['locator'].startswith('obverse.')]
    if not obverse or any(set(e['numeric']) != {'N01'} for e in obverse):
        raise ValueError('This audit requires N01-only obverse entries.')
    total = sum(e['numeric']['N01'] for e in obverse)
    reverse_first = next(e for e in entries if e['locator'] == 'reverse.1.1')
    hypotheses = []
    for ratio in (10, 6):
        reverse_value = sum(count * (ratio if sign == 'N14' else 1)
                            for sign, count in reverse_first['numeric'].items())
        hypotheses.append(dict(assumed_N14_in_N01=ratio,
                               obverse_all_entries=total,
                               reverse_first=reverse_value,
                               difference_obverse_minus_reverse=total-reverse_value))
    return dict(
        source='study/corpus/Uruk_P000928/transliteration.atf',
        source_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
        total_entries=len(entries), obverse_entries=len(obverse),
        reverse_entries=len(entries)-len(obverse),
        obverse_N01_frequency=dict(sorted(Counter(str(e['numeric']['N01']) for e in obverse).items())),
        damaged_numeric_entries=[e['locator'] for e in entries if e['damaged_number']],
        MUSZ3_entries=[e['locator'] for e in entries if 'MUSZ3~a' in e['signs'].split()],
        conditional_totals=hypotheses,
        post_hoc_scope_candidate=dict(excluded_entry='obverse.3.2',
                                     first_ten_N01=sum(e['numeric']['N01'] for e in obverse[:-1]),
                                     remaining_entry_N01=obverse[-1]['numeric']['N01'],
                                     warning='Chosen after observing the sum; not evidence of the last entry function.'),
        assumptions=['Edited counts accepted even where marked damaged.',
                     'All obverse entries use a common additive N01 unit.',
                     'Reverse first entry is compared with the entire obverse.',
                     'Ratios10 and6 are alternatives from scholarship, not a determination for this tablet.'],
        interpretation='Arithmetic diagnostic only; no source correction or ancient error inferred.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = audit(SOURCE.read_text(encoding='utf-8'))
    if args.check:
        if result != json.loads(RESULT.read_text(encoding='utf-8')):
            raise SystemExit('Arithmetic result is stale or different.')
        print('Arithmetic result matches the cited edition and declared assumptions.')
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
