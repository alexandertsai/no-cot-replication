#!/usr/bin/env python3
"""Small native-Anthropic no-CoT replication. Standard library only."""
import argparse, collections, datetime, hashlib, json, os, pathlib, sys, urllib.request, urllib.error
ROOT = pathlib.Path(__file__).resolve().parent
UPSTREAM = pathlib.Path(os.environ.get('NOCOT_BENCH', str(ROOT.parent / 'nocot-bench')))
sys.path.insert(0, str(UPSTREAM))
from nocot.grade import load_bank, grade
from nocot.run import build_messages, NO_DELIB_SYSTEM_TEXT_V2, JSON_SCHEMA_RESPONSE_FORMAT
from nocot.witnesses import is_content_cot
MODEL = 'claude-fable-5-2'
SCHEMA = JSON_SCHEMA_RESPONSE_FORMAT['json_schema']['schema']

def request(bank, item, control=False):
    shots, _ = load_bank(bank, str(UPSTREAM / 'data'))
    messages = build_messages(item, shots, False, None if control else NO_DELIB_SYSTEM_TEXT_V2)
    system = '\n\n'.join(m['content'] for m in messages if m['role']=='system')
    body = dict(model=MODEL, max_tokens=512 if control else 300,
                thinking={'type':'adaptive'},
                output_config={'effort':'high' if control else 'low'},
                messages=[m for m in messages if m['role']!='system'])
    if system: body['system']=system
    if not control: body['output_config']['format']={'type':'json_schema','schema':SCHEMA}
    payload=json.dumps(body).encode()
    req=urllib.request.Request('https://api.anthropic.com/v1/messages', data=payload,
        headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'], 'anthropic-version':'2023-06-01','content-type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=55) as resp: result=json.load(resp)
    except urllib.error.HTTPError as e:
        # Error body only, never request headers or environment values.
        raise RuntimeError(f'HTTP {e.code}: {e.read().decode()[:1200]}') from None
    usage=result.get('usage',{})
    thinking=usage.get('output_tokens_details',{}).get('thinking_tokens')
    text=''.join(c.get('text','') for c in result.get('content',[]) if c.get('type')=='text')
    answer=text
    if not control:
        try: answer=json.loads(text)['answer']
        except (ValueError,KeyError,TypeError): pass
    visible_thinking=any(c.get('type') in ('thinking','redacted_thinking') for c in result.get('content',[]))
    cot=is_content_cot(text,short_answer=True) or is_content_cot(str(answer),short_answer=True)
    blind=thinking is None or not usage.get('output_tokens')
    truncated=result.get('stop_reason')=='max_tokens'
    valid=not blind and thinking==0 and not visible_thinking and not cot and not truncated and bool(str(answer).strip())
    g=grade(str(answer),item,bank)
    rec=dict(model=MODEL,returned_model=result.get("model"),bank=bank,problem_number=item['problem_number'],rung=item['rung'],
             timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),control=control,
             request_sha256=hashlib.sha256(payload).hexdigest(),n_shots=len(shots),
             reasoning_tokens=thinking,usage=usage,stop_reason=result.get('stop_reason'),
             visible_thinking=visible_thinking,content_cot=cot,blind=blind,truncated=truncated,
             valid=valid,answer_correct=bool(g['is_correct']),correct=valid and bool(g['is_correct']))
    return rec, result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('stage',choices=['pilot','control','main','summary']); args=ap.parse_args()
    sets=json.loads((ROOT/'items.json').read_text())
    public=ROOT/'results';public.mkdir(exist_ok=True)
    private=ROOT/'private';private.mkdir(exist_ok=True)
    path=public/'rows.jsonl'
    rows=[json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    if args.stage=='summary':
        summary={}
        for bank in ['arithmetic','brew','shortpath']:
            rr=[r for r in rows if r['stage']=='main' and r['bank']==bank]
            summary[bank]=dict(n=len(rr),correct=sum(r['correct'] for r in rr),invalid=sum(not r['valid'] for r in rr),blind=sum(r['blind'] for r in rr))
        (public/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));return
    if args.stage=='main':
        pilot=[r for r in rows if r['stage']=='pilot']
        controls=[r for r in rows if r['stage']=='control']
        if len(pilot)!=10 or not all(r['valid'] for r in pilot): raise SystemExit('STOP: pilot not clean on both draws')
        if len(controls)!=5 or not all(r['reasoning_tokens'] is not None for r in controls) or not any(r['reasoning_tokens']>0 for r in controls): raise SystemExit('STOP: positive control not validated')
    selection=sets['subset' if args.stage=='main' else 'pilot']
    done={(r['stage'],r['bank'],str(r['problem_number']),r['draw']) for r in rows}
    lookup={b:{str(i['problem_number']):i for i in load_bank(b,str(UPSTREAM/'data'))[1]} for b in {x[0] for x in selection}}
    for draw in range(1,2 if args.stage=='control' else 3):
        for bank,num in selection:
            ident=(args.stage,bank,str(num),draw)
            if ident in done: continue
            # Reuse exact same-recipe pilot requests in the main measurement.
            reused=next((r for r in rows if args.stage=='main' and r['stage']=='pilot' and r['bank']==bank and str(r['problem_number'])==str(num) and r['draw']==draw),None)
            if reused:
                rec={**reused,'stage':'main','reused_pilot':True}
            else:
                rec,raw=request(bank,lookup[bank][str(num)],args.stage=='control')
                rec.update(stage=args.stage,draw=draw)
                with (private/'responses.jsonl').open('a') as f: f.write(json.dumps({'stage':args.stage,'bank':bank,'problem_number':num,'draw':draw,'response':raw})+'\n')
            with path.open('a') as f:f.write(json.dumps(rec)+'\n')
            rows.append(rec)
            print(json.dumps({k:rec[k] for k in ['stage','bank','problem_number','draw','reasoning_tokens','valid','correct','stop_reason']}),flush=True)
            if args.stage=='pilot' and not rec['valid']: raise SystemExit('STOP: unclean pilot; do not expand')
if __name__=='__main__': main()
