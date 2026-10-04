"""Reproduce a numerical reading test from explicitly transcribed observations."""
from pathlib import Path
from fractions import Fraction
import json

root = Path(__file__).resolve().parent
observations = json.loads((root / 'numerical_observations.json').read_text())
control = observations['arithmetic_control']
a = sum(item['counts'][0] for item in control['entries'])
b = sum(item['counts'][1] for item in control['entries'])
c, d = control['total']['counts']
ratio = Fraction(b - d, c - a)
comparisons = []
for candidate in (6, 10):
    entries = [item['counts'][0] * candidate + item['counts'][1] for item in control['entries']]
    written_total = c * candidate + d
    t14, t01 = observations['target']['counts']
    comparisons.append({
        'N14_in_N01_units': candidate,
        'control_entry_values': entries,
        'control_sum': sum(entries),
        'control_written_total': written_total,
        'control_difference': sum(entries) - written_total,
        'control_balances': sum(entries) == written_total,
        'conditional_target_value_in_N01_units': t14 * candidate + t01,
    })
result = {
    'control_id': control['id'],
    'equation': f'{a}r + {b} = {c}r + {d}',
    'derived_N14_to_N01_ratio': str(ratio),
    'assumptions': control['assumptions'],
    'comparisons': comparisons,
    'interpretation_limit': 'The control identifies r=10 only for this control under its assumptions. Neither the numerical system nor the commodity of P281711 follows from this alone.'
}
(root / 'numerical_check_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
