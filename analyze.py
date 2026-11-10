#!/usr/bin/env python3
"""Summarize saved metadata only; never calls an API."""
import collections,json,pathlib,math
root=pathlib.Path(__file__).resolve().parent
rows=[json.loads(l) for l in (root/'results/rows.jsonl').read_text().splitlines()]
main=[r for r in rows if r['stage']=='main']
summary={}
for bank in ['arithmetic','brew','shortpath']:
 rr=[r for r in main if r['bank']==bank]
 byitem=collections.defaultdict(list)
 for r in rr: byitem[str(r['problem_number'])].append(r)
 means=[sum(r['correct'] for r in group)/len(group) for group in byitem.values()]
 n=len(means)
 # Wilson interval for the first draw: each selected item contributes once.
 first=[r for r in rr if r['draw']==1]; nn=len(first); k=sum(r['correct'] for r in first)
 if nn:
  p=k/nn; z=1.95996398454; den=1+z*z/nn
  center=(p+z*z/(2*nn))/den
  half=z*math.sqrt(p*(1-p)/nn+z*z/(4*nn*nn))/den
  interval=[center-half,center+half]
 else: interval=None
 summary[bank]={'responses':len(rr),'unique_items':n,'correct':sum(r['correct'] for r in rr),
 'accuracy':sum(r['correct'] for r in rr)/len(rr) if rr else None,
 'draws':{str(d):{'correct':sum(r['correct'] for r in rr if r['draw']==d),'n':sum(r['draw']==d for r in rr)} for d in [1,2]},
 'first_draw_wilson95':interval,
 'conditional_valid_accuracy':(sum(r['correct'] for r in rr)/sum(r['valid'] for r in rr) if any(r['valid'] for r in rr) else None),
 'invalid':sum(not r['valid'] for r in rr),'blind':sum(r['blind'] for r in rr),
 'rungs':{rung:{'correct':sum(r['correct'] for r in rr if r['rung']==rung),'n':sum(r['rung']==rung for r in rr)} for rung in sorted({r['rung'] for r in rr})}}
# Main pilot reuse records are bookkeeping, not additional API calls.
actual=[r for r in rows if not r.get('reused_pilot')]
usage={key:sum(r['usage'].get(key,0) or 0 for r in actual) for key in ['input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens']}
report={'model':'claude-fable-5-2','tasks':summary,'actual_api_calls':len(actual),'usage':usage,
'pilot':{'n':sum(r['stage']=='pilot' for r in rows),'valid':sum(r['stage']=='pilot' and r['valid'] for r in rows)},
'control':{'n':sum(r['stage']=='control' for r in rows),'nonzero_thinking':sum(r['stage']=='control' and (r['reasoning_tokens'] or 0)>0 for r in rows)},
'main_total_reasoning_tokens':sum(r['reasoning_tokens'] or 0 for r in main),
'notes':['Intervals describe first-draw selected-item variation; repeated draws are not independent extra items.','Five items per rung give limited precision. Three selected domains do not establish an NCRI ranking.','Native usage reports input/output and thinking tokens; an independent total-token discrepancy witness is unavailable.','Dollar cost is not estimated without verified account pricing.']}
(root/'results/summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
