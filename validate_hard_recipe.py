#!/usr/bin/env python3
"""One predeclared prompt-only repair; stop at first invalid response."""
import json,pathlib
from hard_arithmetic import prepare,readrows,PRIV,OUT
from replicate import request
from nocot.run import NO_DELIB_SYSTEM_TEXT_V2
SYSTEM=NO_DELIB_SYSTEM_TEXT_V2+' This is an answer-or-guess task. If the answer is not immediately available, give your best numerical guess immediately. Correctness is secondary to using zero thinking tokens. Do not compute or check intermediate results. Return only the required final-answer JSON.'
ITEM_IDS=['custom-d7-1','custom-d7-2','custom-d7-3','custom-d9-1','custom-d11-1']

def validation_rows():
 p=OUT/'hard_recipe_validation.jsonl'
 return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

if __name__=='__main__':
 items={i['problem_number']:i for i in prepare()}
 meta={'recipe':'answer_or_guess_v1','system':SYSTEM,'validation_item_ids':ITEM_IDS,'criterion':'All five items must be valid on both draws. Stop on first invalid. Selection never depends on correctness.','max_total_inference_calls_including_failed_original':50}
 (OUT/'hard_recipe.json').write_text(json.dumps(meta,indent=2)+'\n')
 rows=validation_rows();done={(r['problem_number'],r['draw']) for r in rows}
 if any(not r['valid'] for r in rows):raise SystemExit('Previously failed validation; no more calls')
 for draw in [1,2]:
  for ident in ITEM_IDS:
   if (ident,draw) in done:continue
   if len(rows)+len(readrows())>=50:raise SystemExit('Total call cap reached')
   item=items[ident];rec,raw=request('arithmetic',item,system_text=SYSTEM)
   rec.update(draw=draw,structural_depth=item['structural_depth'],stage='hard_recipe_validation',recipe='answer_or_guess_v1')
   with (PRIV/'hard_repair_responses.jsonl').open('a') as f:f.write(json.dumps({'problem_number':ident,'draw':draw,'response':raw})+'\n')
   with (OUT/'hard_recipe_validation.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
   rows.append(rec);print(json.dumps({k:rec[k] for k in ['problem_number','draw','reasoning_tokens','valid','correct']}),flush=True)
   if not rec['valid']:raise SystemExit('STOP: repair failed no-CoT validation; do not expand')
 print('Clean on both validation draws; ready for main measurement under separately labelled recipe.')
