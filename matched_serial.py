#!/usr/bin/env python3
"""Matched original Neel serial-task items. $4 cap, no new Astra inference."""
import argparse,collections,datetime,hashlib,json,math,pathlib,random,sys
from replicate import ROOT,UPSTREAM,MODEL,SCHEMA
from budget_continuation import post,billed,readjsonl,append
from nocot.grade import load_bank,grade
from nocot.run import build_messages,NO_DELIB_SYSTEM_TEXT_V2
from nocot.filler import STRONG_NDELIB_TEXT
from nocot.witnesses import is_content_cot
DATA=UPSTREAM/'data';OUT=ROOT/'results';PRIV=ROOT/'private'
ROWS=OUT/'matched_rows.jsonl';LEDGER=PRIV/'matched_ledger.jsonl';CAP=4.0;SEED=20261112
FAMILIES=['arithmetic','brew','chain','cfgpatch']
HARD={'arithmetic':'arithmetic_hi','brew':'brew_v2s','chain':'chain_hi','cfgpatch':'cfgpatch_hi'}
RECIPES=[
 {'name':'v2_schema','system':'v2','schema':True,'shots':'canonical'},
 {'name':'strong_plain','system':'strong','schema':False,'shots':'canonical'},
 {'name':'strong_schema','system':'strong','schema':True,'shots':'canonical'},
 {'name':'strong_plain_hard3','system':'strong','schema':False,'shots':'hard3'},
 {'name':'strong_schema_hard3','system':'strong','schema':True,'shots':'hard3'},
 {'name':'strong_plain_one','system':'strong','schema':False,'shots':'one'},
 {'name':'strong_schema_zero','system':'strong','schema':True,'shots':'zero'},
 {'name':'strong_plain_zero','system':'strong','schema':False,'shots':'zero'}]

def bank(name):
 try:return load_bank(name,str(DATA))
 except KeyError:
  meta=json.loads((DATA/'extras_diagnostics.json').read_text())
  desc=meta['extras'].get(name) or meta['diagnostics'].get(name)
  if not desc:raise
  rr=readjsonl(DATA/desc['file'])
  return [r for r in rr if r.get('split')=='shot'],[r for r in rr if r.get('split')=='eval']

def key(bankname,number):return bankname+':'+str(number)
def published():return {key(r['bank'],r['problem_number']):r for r in readjsonl(DATA/'rows/complete__openai_gpt-6-astra.jsonl')}

def prepare():
 OUT.mkdir(exist_ok=True);PRIV.mkdir(exist_ok=True)
 path=PRIV/'matched_items.json'
 if path.exists():return json.loads(path.read_text())
 baseline=published();past={(r['bank'],str(r['problem_number'])) for r in readjsonl(OUT/'rows.jsonl') if r['stage']=='main'}
 rng=random.Random(SEED);selected=[];probes=[];demos={}
 low={'arithmetic':{2,3,4},'brew':{1,2},'chain':{2,3},'cfgpatch':{2,3}}
 mid={'arithmetic':{6,7,8,10,12},'brew':{3,4,5},'chain':{5,6,8},'cfgpatch':{5,6}}
 for family in FAMILIES:
  _,base=bank(family);_,hard=bank(HARD[family])
  pools={'low':[(family,i) for i in base if i.get('difficulty') in low[family]],'mid':[(family,i) for i in base if i.get('difficulty') in mid[family]],'hard':[(HARD[family],i) for i in hard if family!='brew' or i.get('h')==7]}
  used=set()
  for stratum,pool in pools.items():
   eligible=[(b,i) for b,i in pool if key(b,i['problem_number']) in baseline and (b,str(i['problem_number'])) not in past]
   # Round-robin shuffled nominal difficulty levels; never inspect baseline correctness.
   groups=collections.defaultdict(list)
   for b,i in sorted(eligible,key=lambda x:str(x[1]['problem_number'])):groups[i.get('difficulty')].append((b,i))
   for group in groups.values():rng.shuffle(group)
   ordered=[]
   while any(groups.values()):
    for level in sorted(groups):
     if groups[level]:ordered.append(groups[level].pop())
   n_probe=1 if stratum=='low' else 2
   if len(ordered)<5+n_probe:raise RuntimeError('Not enough untouched original items')
   for idx,(b,i) in enumerate(ordered[:5+n_probe]):
    rec={'family':family,'bank':b,'stratum':stratum,'id':key(b,i['problem_number']),'item':i}
    (selected if idx<5 else probes).append(rec);used.add(rec['id'])
  available=[{'family':family,'bank':HARD[family],'id':key(HARD[family],i['problem_number']),'item':i} for i in hard if key(HARD[family],i['problem_number']) not in used]
  rng.shuffle(available);demos[family]=available[:3]
 payload={'main':selected,'probes':probes,'demos':demos}
 path.write_text(json.dumps(payload,indent=2)+'\n')
 def publicrec(r):
  return {'family':r['family'],'bank':r['bank'],'problem_number':r['item']['problem_number'],'stratum':r.get('stratum','demonstration'),'nominal_difficulty':r['item'].get('difficulty'),'rung':r['item'].get('rung'),'problem_sha256':hashlib.sha256(r['item']['problem'].encode()).hexdigest()}
 manifest={'seed':SEED,'upstream_commit':json.loads((ROOT/'plan.json').read_text())['repository_commit'],'selection':'15 per family: five low, five mid, five hard, round-robin across nominal difficulty levels with seeded random item order. Selection never uses Astra outcomes. Previous Fable main items excluded.','main':[publicrec(r) for r in selected],'probes':[publicrec(r) for r in probes],'hard_demos':{f:[publicrec(r) for r in rr] for f,rr in demos.items()},'note':'Hard supplemental items include unscored NCRI rungs; this is a matched diagnostic, not an NCRI score. brew_v2s h7 is used instead of the explicitly breadth-confounded brew_hi. Arithmetic operator counts and other difficulty labels are not cross-task equivalent serial depths.','astra':'One published Astra response per selected item. Fable has two new independent draws. Do not count duplicated baseline references as extra Astra draws.'}
 (OUT/'matched_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 return payload

def body(rec,recipe,payload,control=False):
 if recipe['shots']=='hard3':shots=[r['item'] for r in payload['demos'][rec['family']]]
 else:
  shots,_=bank(rec['family'])
  if recipe['shots']=='one':shots=shots[:1]
  elif recipe['shots']=='zero':shots=[]
 system=NO_DELIB_SYSTEM_TEXT_V2+('\n\n'+STRONG_NDELIB_TEXT if recipe['system']=='strong' else '')
 msgs=build_messages(rec['item'],shots,False,None if control else system)
 b={'model':MODEL,'messages':[m for m in msgs if m['role']!='system'],'thinking':{'type':'adaptive'},'output_config':{'effort':'max' if control else 'low'},'max_tokens':512 if control else (300 if recipe['schema'] else 100)}
 ss=[m['content'] for m in msgs if m['role']=='system']
 if ss:b['system']='\n\n'.join(ss)
 if recipe['schema'] and not control:b['output_config']['format']={'type':'json_schema','schema':SCHEMA}
 return b

def budget_upper():
 settled={r['id']:r for r in readjsonl(ROWS)}
 return 1.1*sum(r['estimated_standard_usd'] for r in settled.values())+sum(r['reserved_usd'] for r in readjsonl(LEDGER) if r['id'] not in settled)

def classify(text,answer,thinking,thinking_block,blind,truncated,item,family):
 cot=is_content_cot(text,short_answer=True) or is_content_cot(str(answer),short_answer=True)
 valid=not blind and not truncated and thinking==0 and not thinking_block and not cot and bool(str(answer).strip())
 g=grade(str(answer),item,family)
 return {'valid':valid,'answer_correct':bool(g['is_correct']),'correct':valid and bool(g['is_correct']),'content_cot':cot,'missing':blind or truncated}

def call(rec,recipe,payload,phase,draw):
 ident=f"{rec['family']}:{recipe['name']}:{phase}:{rec['id']}:{draw}"
 rows=readjsonl(ROWS);existing=next((r for r in rows if r['id']==ident),None)
 if existing:return existing
 b=body(rec,recipe,payload,phase=='control')
 count=post('messages/count_tokens',{k:v for k,v in b.items() if k!='max_tokens'})['input_tokens']
 reserve=1.2*((math.ceil(count*1.25)+256)*8+b['max_tokens']*40)/1e6
 if budget_upper()+reserve>CAP:raise SystemExit('Matched $4 cap: refusing request before transmission')
 if any(r['id']==ident for r in readjsonl(LEDGER)):raise SystemExit('Unsettled previous request: no automatic retry')
 append(LEDGER,{'id':ident,'reserved_usd':reserve,'input_count':count,'max_output_tokens':b['max_tokens']})
 response=post('messages',b);usage=response.get('usage',{});cost=billed(usage)
 append(PRIV/'matched_responses.jsonl',{'id':ident,'response':response})
 if cost>reserve:raise SystemExit('Unexpected usage exceeds reservation; stop')
 text=''.join(x.get('text','') for x in response.get('content',[]) if x.get('type')=='text');answer=text
 try:
  parsed=json.loads(text)
  if isinstance(parsed,dict) and 'answer' in parsed:answer=parsed['answer']
 except (ValueError,TypeError):pass
 rt=usage.get('output_tokens_details',{}).get('thinking_tokens');tb=any(x.get('type') in ['thinking','redacted_thinking'] for x in response.get('content',[]))
 blind=rt is None or not usage.get('input_tokens') or not usage.get('output_tokens');truncated=response.get('stop_reason')=='max_tokens'
 row={'id':ident,'family':rec['family'],'bank':rec['bank'],'problem_number':rec['item']['problem_number'],'stratum':rec['stratum'],'nominal_difficulty':rec['item'].get('difficulty'),'phase':phase,'recipe':recipe['name'],'draw':draw,'model':MODEL,'returned_model':response.get('model'),'reasoning_tokens':rt,'thinking_block':tb,'blind':bool(blind),'truncated':truncated,'stop_reason':response.get('stop_reason'),'usage':usage,'estimated_standard_usd':cost,'reserved_usd':reserve,'request_sha256':hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest(),**classify(text,answer,rt,tb,blind,truncated,rec['item'],rec['family'])}
 append(ROWS,row)
 print(json.dumps({k:row[k] for k in ['phase','family','recipe','stratum','problem_number','draw','reasoning_tokens','valid','correct','estimated_standard_usd']}),flush=True)
 return row

def astra_rows(payload):
 source=published();result=[]
 for rec in payload['main']:
  r=source[rec['id']];w=r['witnesses'];text=r['raw_text'];answer=text
  try:
   obj=json.loads(text)
   if isinstance(obj,dict) and 'answer' in obj:answer=obj['answer']
  except (ValueError,TypeError):pass
  rt=w.get('reasoning_tokens');blind=not w.get('rtok_field_present') or rt is None or not w.get('completion_tokens')
  trunc=w.get('finish_reason')=='length' or w.get('native_finish_reason')=='max_tokens'
  verdict=classify(text,answer,rt,False,blind,trunc,rec['item'],rec['family'])
  if (w.get('hidden_channel_tokens') or 0)>0:verdict.update(valid=False,correct=False)
  result.append({'family':rec['family'],'bank':rec['bank'],'problem_number':rec['item']['problem_number'],'stratum':rec['stratum'],'nominal_difficulty':rec['item'].get('difficulty'),'model':'openai_gpt-6-astra','published_draw':r['draw'],'published_arm':r['arm'],'published_correct':r['verdict']['correct'],'published_valid':r['verdict']['valid'],'reasoning_tokens':rt,'blind':blind,'truncated':trunc,**verdict})
 (OUT/'matched_astra.json').write_text(json.dumps({'source':'https://github.com/neelnanda-io/nocot-bench','rows':result},indent=2)+'\n')
 return result

def preflight(payload):
 counts=[]
 for rec in payload['main']:
  b=body(rec,RECIPES[0],payload)
  n=post('messages/count_tokens',{k:v for k,v in b.items() if k!='max_tokens'})['input_tokens']
  counts.append({'family':rec['family'],'bank':rec['bank'],'problem_number':rec['item']['problem_number'],'input_tokens':n})
 report={'reference_recipe':RECIPES[0],'counts':counts,'main_120_input_tokens':2*sum(r['input_tokens'] for r in counts),'main_expected_standard_usd_at_12_output_tokens_per_response':2*sum(r['input_tokens'] for r in counts)*8/1e6+120*12*40/1e6,'note':'Forecast only; validation can choose other recipes. Actual per-request counts and budget guard apply before every inference call.'}
 (OUT/'matched_preflight.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='counts'}))

def run(payload):
 plan={'cap_usd':4,'scope':'This matched-original-item run only.','recipes_in_order':RECIPES,'selection':'Per family, first recipe clean on one low/mid/hard screen and then five disjoint-from-main probe items on two draws. Screen responses are reused as the corresponding validation draw, not repurchased. Never select by accuracy.','main':'Exactly 15 frozen original items per family, two Fable draws each. A family without validated no-CoT recipe is unmeasured, not silently omitted or scored zero.','positive_control':'One maximum-effort probe per measured family must have a present, nonzero thinking-token counter.','pricing_source':'https://platform.claude.com/docs/en/models/fable-5-2/whats-new-fable-5-2','budget':'Completed usage retained at 1.1 times standard cost, outstanding requests at full reservation. The settled margin was reduced from 1.2 after 169 completed calls; see matched_completion_plan.json. Reserve next request with 25%+256 extra input tokens and full max output, all at 1.2x standard rates. Require total <=$4 before transmitting. No automatic retries.','ledger':'Local private/matched_ledger.jsonl; never publish.','comparison':'Regrade both models using same upstream answer grader and normalize JSON answers consistently. Nontruncated reasoning is wrong; truncation/blind is missing. Report matched nonmissing pairs and separate missingness/invalidity.'}
 (OUT/'matched_plan.json').write_text(json.dumps(plan,indent=2)+'\n');chosen={}
 for family in FAMILIES:
  probes=[r for r in payload['probes'] if r['family']==family]
  # One low, one mid, one hard before filling out five probes on two draws.
  screen=[next(r for r in probes if r['stratum']==s) for s in ['low','mid','hard']]
  recipe=None
  for candidate in RECIPES:
   sr=[call(r,candidate,payload,'probe',1) for r in screen]
   if not all(r['valid'] for r in sr):continue
   vr=[call(r,candidate,payload,'probe',draw) for draw in [1,2] for r in probes]
   if all(r['valid'] for r in vr):recipe=candidate;break
  if recipe is None:
   chosen[family]={'status':'no_clean_recipe'};continue
  chosen[family]={'status':'validated','recipe':recipe}
  control=call(probes[-1],recipe,payload,'control',1)
  if control['reasoning_tokens'] is None or control['reasoning_tokens']==0:
   chosen[family]['status']='positive_control_failed';continue
  for draw in [1,2]:
   for rec in payload['main']:
    if rec['family']==family:call(rec,recipe,payload,'main',draw)
  (OUT/'matched_recipes.json').write_text(json.dumps(chosen,indent=2)+'\n')
 (OUT/'matched_recipes.json').write_text(json.dumps(chosen,indent=2)+'\n');summarize(payload)

def summarize(payload):
 astra=astra_rows(payload);rows=readjsonl(ROWS);main=[r for r in rows if r['phase']=='main'];table={}
 for family in FAMILIES:
  ar=[r for r in astra if r['family']==family];fr=[r for r in main if r['family']==family]
  def stats(rr):
   sc=[r for r in rr if not r['missing']];invalid=sum(not r['valid'] for r in sc)
   return {'responses':len(rr),'scorable':len(sc),'correct':sum(r['correct'] for r in sc),'accuracy':sum(r['correct'] for r in sc)/len(sc) if sc else None,'invalid':invalid,'missing':sum(r['missing'] for r in rr),'cell_unmeasured_over20pct_invalid':5*invalid>len(sc) if sc else True,'incomplete_over20pct_missing':5*sum(r['missing'] for r in rr)>len(rr) if rr else True}
  draws={}
  for draw in [1,2]:
   ff=[r for r in fr if r['draw']==draw];pairs=[]
   for f in ff:
    a=next(a for a in ar if a['bank']==f['bank'] and str(a['problem_number'])==str(f['problem_number']))
    if not f['missing'] and not a['missing']:pairs.append((f,a))
   draws[str(draw)]={'fable':stats(ff),'paired':{'n':len(pairs),'fable_correct':sum(f['correct'] for f,a in pairs),'astra_correct':sum(a['correct'] for f,a in pairs),'fable_only':sum(f['correct'] and not a['correct'] for f,a in pairs),'astra_only':sum(a['correct'] and not f['correct'] for f,a in pairs)}}
  table[family]={'astra':stats(ar),'fable_draws':draws,'strata':{s:{'astra':stats([r for r in ar if r['stratum']==s]),'fable':{str(d):stats([r for r in fr if r['stratum']==s and r['draw']==d]) for d in [1,2]}} for s in ['low','mid','hard']}}
 report={'scope':'60 original items, four serial families, one fixed published Astra response/item, two new Fable draws where no-CoT validates. Not a normalized depth estimate or overall NCRI.','cap_usd':CAP,'estimated_standard_usd':sum(r['estimated_standard_usd'] for r in rows),'conservative_committed_usd':budget_upper(),'inference_calls':len({r['id'] for r in rows}|{r['id'] for r in readjsonl(LEDGER)}),'responses_received':len(rows),'usage':{k:sum(r['usage'].get(k,0) for r in rows) for k in ['input_tokens','output_tokens']},'tasks':table,'notes':['Both models regraded using the same shared grader; published Astra verdicts retained for audit.','Truncated and blind responses are missing, never silently counted as correct or as zero reasoning.','Paired comparisons exclude a pair only for missingness; nontruncated reasoned responses remain wrong.','Primary comparison uses Fable draw1, with draw2 a serving repeat, not new independent items.','Within-family >20% invalid among scorable responses is flagged unmeasured; do not claim a capability ranking from an invalid cell.','Difficulty labels are task-specific, not comparable arithmetic-step units.','No new Astra inference or public spending ledger.']}
 (OUT/'matched_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'cost':report['estimated_standard_usd'],'calls':len(rows),'tasks':{f:{'astra':v['astra'],'draws':v['fable_draws']} for f,v in table.items()}},indent=2))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','preflight','run','summary']);a=ap.parse_args();p=prepare()
 if a.stage=='prepare':print('Frozen main',len(p['main']),'probe',len(p['probes']),'demo',sum(map(len,p['demos'].values())));astra_rows(p)
 elif a.stage=='preflight':preflight(p)
 elif a.stage=='run':
  try:run(p)
  finally:summarize(p)
 else:summarize(p)
