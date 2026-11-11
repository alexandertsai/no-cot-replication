#!/usr/bin/env python3
"""Post-declared exploratory completion under unchanged $4 token-spend cap."""
import json
import matched_serial as m

def main():
 p=m.prepare();recipe=next(r for r in m.RECIPES if r['name']=='strong_schema_zero')
 chosenpath=m.OUT/'matched_recipes.json'
 chosen=json.loads(chosenpath.read_text()) if chosenpath.exists() else {}
 for family in ['brew','cfgpatch']:
  probes=[r for r in p['probes'] if r['family']==family]
  # These are existing probe records. Refuse if their reported validity changed.
  rows=[r for r in m.readjsonl(m.ROWS) if r['phase']=='probe' and r['family']==family and r['recipe']==recipe['name']]
  observed_valid=sum(r['valid'] for r in rows)
  if len(rows)!=10 or observed_valid<8:raise SystemExit('Validation below exploratory completion threshold; do not buy automatically')
  control=m.call(probes[-1],recipe,p,'control',1)
  if control['reasoning_tokens'] is None or control['reasoning_tokens']==0:raise SystemExit('Positive control failed')
  chosen[family]={'status':'exploratory_completion_partial_validation','recipe':recipe,'probe_valid':observed_valid,'probe_n':10}
  chosenpath.write_text(json.dumps(chosen,indent=2)+'\n')
  for draw in [1,2]:
   for rec in p['main']:
    if rec['family']==family:m.call(rec,recipe,p,'main',draw)
 m.summarize(p)
if __name__=='__main__':
 try:main()
 finally:m.summarize(m.prepare())
