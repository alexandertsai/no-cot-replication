#!/usr/bin/env python3
"""Budgeted no-CoT recipe search and held-out depth diagnostic. No dependencies."""
import collections,datetime,hashlib,json,math,os,pathlib,sys,urllib.request,urllib.error
from replicate import MODEL,SCHEMA,UPSTREAM
from hard_arithmetic import prepare,OUT,PRIV
from nocot.grade import load_bank,grade
from nocot.run import build_messages,NO_DELIB_SYSTEM_TEXT_V2
from nocot.filler import STRONG_NDELIB_TEXT
from nocot.witnesses import is_content_cot
CAP=4.0
LEDGER=PRIV/'continuation_ledger.jsonl'
ROWS=OUT/'continuation_rows.jsonl'
# Screening and validation items are separate from the future measured 1..5 items.
SCREEN=['custom-d7-6','custom-d9-6','custom-d11-6']
VALIDATE=['custom-d5-6','custom-d6-6',*SCREEN]
RECIPES=[
 {'name':'plain_k10','shots':'standard10','system':'v2','schema':False},
 {'name':'plain_k1','shots':'standard1','system':'v2','schema':False},
 {'name':'schema_k1','shots':'standard1','system':'v2','schema':True},
 {'name':'strong_plain_k10','shots':'standard10','system':'strong','schema':False},
 {'name':'strong_plain_k1','shots':'standard1','system':'strong','schema':False},
 {'name':'strong_schema_k1','shots':'standard1','system':'strong','schema':True},
 {'name':'strong_plain_hard10','shots':'hard10','system':'strong','schema':False},
 {'name':'strong_schema_hard10','shots':'hard10','system':'strong','schema':True}]
RATES={'input_per_million':8,'output_per_million':40,'cache_write_5m_per_million':10,'cache_write_1h_per_million':16,'cache_read_per_million':0.20}

def readjsonl(path):return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
def append(path,obj):
 with path.open('a') as f:f.write(json.dumps(obj)+'\n')
def billed(usage):
 # No caching is requested, but account for any returned cache usage conservatively.
 return (8*usage.get('input_tokens',0)+40*usage.get('output_tokens',0)+16*usage.get('cache_creation_input_tokens',0)+0.20*usage.get('cache_read_input_tokens',0))/1e6

def budget_upper():
 settled={r['id']:r for r in readjsonl(ROWS)}
 return 2*sum(r['estimated_standard_usd'] for r in settled.values())+sum(x['reserved_usd'] for x in readjsonl(LEDGER) if x['id'] not in settled)

def headers():return {'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01','content-type':'application/json'}
def post(path,body):
 req=urllib.request.Request('https://api.anthropic.com/v1/'+path,data=json.dumps(body).encode(),headers=headers())
 try:
  with urllib.request.urlopen(req,timeout=55) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError(f'HTTP {e.code}: {e.read().decode()[:700]}') from None

def build(item,recipe,items,control=False):
 standard,_=load_bank('arithmetic',str(UPSTREAM/'data'))
 if recipe['shots']=='hard10':
  shotids=[f'custom-d7-{j}' for j in [7,8,9]]+[f'custom-d9-{j}' for j in [7,8,9]]+[f'custom-d11-{j}' for j in [7,8,9,10]]
  shots=[items[x] for x in shotids]
 else:shots=standard[:1] if recipe['shots']=='standard1' else standard
 system=NO_DELIB_SYSTEM_TEXT_V2
 if recipe['system']=='strong':system+='\n\n'+STRONG_NDELIB_TEXT
 msgs=build_messages(item,shots,False,None if control else system)
 body={'model':MODEL,'messages':[m for m in msgs if m['role']!='system'],'thinking':{'type':'adaptive'},'output_config':{'effort':'max' if control else 'low'},'max_tokens':512 if control else (300 if recipe['schema'] else 100)}
 sysmsgs=[m['content'] for m in msgs if m['role']=='system']
 if sysmsgs:body['system']='\n\n'.join(sysmsgs)
 if recipe['schema'] and not control:body['output_config']['format']={'type':'json_schema','schema':SCHEMA}
 return body

def call(item,recipe,items,phase,draw=1):
 existing=[r for r in readjsonl(ROWS) if r['problem_number']==item['problem_number'] and r['recipe']==recipe['name'] and r['phase']==phase and r['draw']==draw]
 if existing:return existing[0]
 body=build(item,recipe,items,phase=='control')
 countbody={k:v for k,v in body.items() if k!='max_tokens'}
 count=post('messages/count_tokens',countbody)['input_tokens']
 # Reserve doubles standard rates, allows 25% + 256 input-token overhead,
 # and charges max output. Settled requests retain 2x observed cost; unknown
 # requests keep their full reservation.
 reserve=(math.ceil(count*1.25)+256)*16/1e6+body['max_tokens']*80/1e6
 ledger=readjsonl(LEDGER);reserved=budget_upper()
 if reserved+reserve>CAP:raise SystemExit('Dollar cap: refusing next request before transmission')
 ident=f'{recipe["name"]}:{phase}:{item["problem_number"]}:{draw}'
 if any(x['id']==ident for x in ledger):raise SystemExit('Unsettled prior request; do not automatically retry')
 append(LEDGER,{'id':ident,'reserved_usd':reserve,'counted_input_tokens':count,'max_output_tokens':body['max_tokens'],'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 result=post('messages',body)
 usage=result.get('usage',{})
 actual=billed(usage)
 if actual>reserve:raise SystemExit('Unexpected price/usage above reserve; stopping immediately')
 text=''.join(b.get('text','') for b in result.get('content',[]) if b.get('type')=='text')
 rt=usage.get('output_tokens_details',{}).get('thinking_tokens')
 answer=text
 if recipe['schema'] and phase!='control':
  try:answer=json.loads(text)['answer']
  except (ValueError,KeyError,TypeError):pass
 cot=is_content_cot(text,short_answer=True) or is_content_cot(str(answer),short_answer=True)
 thinking_block=any(b.get('type') in ['thinking','redacted_thinking'] for b in result.get('content',[]))
 blind=rt is None or not usage.get('output_tokens')
 truncated=result.get('stop_reason')=='max_tokens'
 valid=not blind and rt==0 and not thinking_block and not cot and not truncated and bool(str(answer).strip())
 scored=grade(str(answer),item,'arithmetic')
 rec={'id':ident,'model':MODEL,'returned_model':result.get('model'),'recipe':recipe['name'],'phase':phase,'draw':draw,'problem_number':item['problem_number'],'depth':item['structural_depth'],'usage':usage,'reasoning_tokens':rt,'thinking_block':thinking_block,'content_cot':cot,'blind':blind,'truncated':truncated,'stop_reason':result.get('stop_reason'),'valid':valid,'answer_correct':bool(scored['is_correct']),'correct':valid and bool(scored['is_correct']),'estimated_standard_usd':actual,'reserved_usd':reserve,'counted_input_tokens':count,'request_sha256':hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()}
 append(PRIV/'continuation_responses.jsonl',{'id':ident,'response':result})
 append(ROWS,rec)
 print(json.dumps({k:rec[k] for k in ['phase','recipe','problem_number','draw','reasoning_tokens','valid','correct','estimated_standard_usd']}),flush=True)
 return rec

def main():
 items={i['problem_number']:i for i in prepare()}
 plan={'cap_usd':CAP,'cap_scope':'This continuation only, after the previous two probes.','rates':RATES,'pricing_source':'https://platform.claude.com/docs/en/models/fable-5-2/whats-new-fable-5-2','reservation':'Before each transmission, twice the standard-price cost of settled responses plus all unsettled worst-case reservations plus the next worst-case reservation must be <= $4. Reserve uses 2x standard rates, 25% + 256 prompt-token allowance, and max output. Unused reservation is released only after usage arrives. No automatic retries.','recipes':RECIPES,'screen_ids':SCREEN,'validation_ids':VALIDATE,'selection':'First recipe clean on 3 screen items plus 5 validation items on two draws; order fixed before inference, never select by accuracy. Separate held-out main items.','main':'5 held-out items/depth, 2 draws at 7,9,11; predefined downward expansion to 5 and 6; one additional post-declared depth4 anchor, recorded in continuation_budget_revision.json.','invalid_policy':'Screen failures reject a recipe, not the whole search. Nontruncated main reasoned rows score wrong; truncated/blind rows are missing. >20% invalid among scorable rows marks unmeasured; >20% missing is separately flagged as incomplete.','fresh_control':'One max-effort control on a screening item; counter must be present and >0.','structural_caveat':'These synthetic sensitivity-filtered diagnostic depths are not the normalized 7.2-step metric.'}
 (OUT/'continuation_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 chosen=None
 for recipe in RECIPES:
  screen=[call(items[x],recipe,items,'screen') for x in SCREEN]
  if not all(r['valid'] for r in screen):continue
  validation=[call(items[x],recipe,items,'validation',draw) for draw in [1,2] for x in VALIDATE]
  if all(r['valid'] for r in validation):chosen=recipe;break
 if chosen is None:
  summarize();print('No recipe passed clean two-draw validation; no held-out evaluation purchased.');return
 (OUT/'continuation_chosen_recipe.json').write_text(json.dumps(chosen,indent=2)+'\n')
 control=call(items[SCREEN[0]],chosen,items,'control')
 if control['reasoning_tokens'] is None or control['reasoning_tokens']==0:raise SystemExit('Positive control failed; no main purchases')
 for depth in [7,9,11]:
  for draw in [1,2]:
   for j in range(1,6):call(items[f'custom-d{depth}-{j}'],chosen,items,'main',draw)
 # Freeze expansion based on primary main scores, never substitute easier items.
 rows=[r for r in readjsonl(ROWS) if r['phase']=='main'];acc={d:sum(r['correct'] for r in rows if r['depth']==d)/sum(r['depth']==d for r in rows) for d in [7,9,11]}
 if acc[7]<0.5:extra=[5,6]
 elif acc[9]<0.5:extra=[8,6]
 elif acc[11]<0.5:extra=[10,8]
 else:extra=[]
 for depth in extra:
  for draw in [1,2]:
   for j in range(1,6):call(items[f'custom-d{depth}-{j}'],chosen,items,'main',draw)
 # One additional low-depth anchor, declared after the first 5/6/7 results.
 if extra==[5,6]:
  for draw in [1,2]:
   for j in range(1,6):call(items[f'custom-d4-{j}'],chosen,items,'main',draw)
 summarize()

def summarize():
 rows=readjsonl(ROWS);ledger=readjsonl(LEDGER)
 recipes={}
 for name in [r['name'] for r in RECIPES]:
  rr=[r for r in rows if r['recipe']==name and r['phase']!='control']
  if rr:recipes[name]={'responses':len(rr),'valid':sum(r['valid'] for r in rr),'reasoned':sum((r['reasoning_tokens'] or 0)>0 for r in rr),'blind':sum(r['blind'] for r in rr),'truncated':sum(r['truncated'] for r in rr),'estimated_standard_usd':sum(r['estimated_standard_usd'] for r in rr)}
 main=[r for r in rows if r['phase']=='main'];table={}
 for d in sorted({r['depth'] for r in main}):
  rr=[r for r in main if r['depth']==d];valid=sum(r['valid'] for r in rr)
  measured=[r for r in rr if not r['truncated'] and not r['blind']]
  invalid=sum(not r['valid'] for r in measured)
  primary=sum(r['correct'] for r in measured)/len(measured) if measured else None
  table[str(d)]={'n_items':len({r['problem_number'] for r in rr}),'n_responses':len(rr),'scorable':len(measured),'valid':valid,'invalid_nontruncated':invalid,'truncated_missing':sum(r['truncated'] for r in rr),'blind_missing':sum(r['blind'] for r in rr),'correct':sum(r['correct'] for r in measured),'floor_accuracy':primary,'all_attempt_success_rate':sum(r['correct'] for r in rr)/len(rr),'conditional_valid_ceiling':sum(r['correct'] for r in rr)/valid if valid else None,'unmeasured_nonvalid_above_20pct':invalid/len(measured)>0.20 if measured else True,'incomplete_over_20pct_missing':1-len(measured)/len(rr)>0.20,'draws':{str(draw):{'attempts':sum(r['draw']==draw for r in rr),'n':sum(r['draw']==draw for r in measured),'correct':sum(r['draw']==draw and r['correct'] for r in measured)} for draw in [1,2]}}
 report={'cap_usd':CAP,'reserved_upper_usd':budget_upper(),'gross_historical_reservations_usd':sum(r['reserved_usd'] for r in ledger),'estimated_standard_usd':sum(r['estimated_standard_usd'] for r in rows),'inference_requests_reserved':len(ledger),'responses_received':len(rows),'input_tokens':sum(r['usage'].get('input_tokens',0) for r in rows),'output_tokens':sum(r['usage'].get('output_tokens',0) for r in rows),'recipes':recipes,'main':table,'headline_normalized_threshold':None,'notes':['Dollar figures use published standard token rates, not a retrieved invoice. Reserved upper bound is deliberately conservative.','Nontruncated no-CoT-invalid answers are wrong in the primary score. Truncated/blind responses are missing, not scored wrong; all-attempt success is a separate diagnostic. Missing/blind counters are never treated as zero.','Validation is selected only on cleanliness; score comparison uses held-out items.','A single-family structural/sensitivity-filtered threshold cannot be equated with Neel\'s normalized cross-task estimate.']}
 fitpath=OUT/'continuation_depth_fit.json'
 if fitpath.exists():
  fit=json.loads(fitpath.read_text())
  report['descriptive_depth50_by_draw']={d:r['depth50'] for d,r in fit['fits'].items()}
  report['depth_fit_details']='continuation_depth_fit.json'
 (OUT/'continuation_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='summary':summarize()
 else:main()
