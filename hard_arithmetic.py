#!/usr/bin/env python3
"""Audited synthetic arithmetic-depth extension; at most 50 inference calls."""
import ast, collections, hashlib, json, operator, pathlib, random, sys, urllib.request, os
from replicate import ROOT, UPSTREAM, request, SCHEMA, MODEL
from depth_analysis import structural_depth
sys.path.insert(0,str(UPSTREAM))
from datagen.banks.arithmetic import _gen_expr, Config, INSTRUCTION
from nocot.grade import load_bank
from nocot.run import build_messages, NO_DELIB_SYSTEM_TEXT_V2
OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod}
SEED=20261111
PRIV=ROOT/'private';OUT=ROOT/'results'

def evaluate(n,override=None,delta=0,values=None):
    if isinstance(n,ast.Constant):v=n.value
    elif isinstance(n,ast.UnaryOp):v=-evaluate(n.operand,override,delta,values) if isinstance(n.op,ast.USub) else evaluate(n.operand,override,delta,values)
    elif isinstance(n,ast.BinOp):v=OPS[type(n.op)](evaluate(n.left,override,delta,values),evaluate(n.right,override,delta,values))
    else:raise ValueError('Unsupported syntax')
    if n is override:v+=delta
    if abs(v)>10**10:raise ValueError('Intermediate too large')
    if values is not None:values[id(n)]=v
    return v

def audit(expression):
    n=ast.parse(expression,mode='eval').body
    values={};gold=evaluate(n,values=values)
    if abs(gold)>10**7:raise ValueError('Answer too large')
    nodes=[x for x in ast.walk(n) if isinstance(x,ast.BinOp)]
    # Reject immediately redundant operations on these particular values.
    if any(values[id(x)] in (values[id(x.left)],values[id(x.right)]) for x in nodes):raise ValueError('Identity/absorbing operation')
    sensitive={}
    for x in nodes:
        try:sensitive[id(x)]=all(evaluate(n,x,d)!=gold for d in [-1,1])
        except (ZeroDivisionError,ValueError):sensitive[id(x)]=False
    def path(x):
        if isinstance(x,ast.UnaryOp):return path(x.operand)
        if not isinstance(x,ast.BinOp):return 0
        return (1+max(path(x.left),path(x.right))) if sensitive[id(x)] else 0
    depth=structural_depth(n)
    if path(n)!=depth:raise ValueError('Longest chain fails +/-1 sensitivity audit')
    return gold,depth,len(nodes)

def prepare():
    PRIV.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
    p=PRIV/'hard_items.json'
    if p.exists():return json.loads(p.read_text())
    rng=random.Random(SEED);cfg=Config();items=[];seen=set()
    # Freeze initial and reserve items before looking at any model result.
    # Reserve lower levels permit a downward bracket if all initial levels fail.
    for depth in [4,5,6,7,8,9,10,11]:
        accepted=0
        for attempt in range(200000):
            expr=_gen_expr(rng.randint(depth,2*depth+2),rng,cfg)
            if expr in seen:continue
            node=ast.parse(expr,mode='eval').body
            if structural_depth(node)!=depth:continue
            try:gold,d,ops=audit(expr)
            except (ZeroDivisionError,ValueError):continue
            item={'domain':'arithmetic','problem_number':f'custom-d{d}-{accepted+1}', 'rung':f'custom_arithmetic:depth{d}', 'problem':'Evaluate this Python expression. '+expr,'answer':gold,'instruction':INSTRUCTION,'structural_depth':d,'binary_operator_count':ops,'expression_sha256':hashlib.sha256(expr.encode()).hexdigest()}
            items.append(item);seen.add(expr);accepted+=1
            if accepted==10:break
        if accepted!=10:raise RuntimeError(f'Could not prepare depth {depth}')
    p.write_text(json.dumps(items,indent=2)+'\n')
    public={k:[{z:i[z] for z in ['problem_number','structural_depth','binary_operator_count','expression_sha256']} for i in items if i['structural_depth']==k] for k in sorted({i['structural_depth'] for i in items})}
    (OUT/'hard_manifest.json').write_text(json.dumps({'seed':SEED,'initial_depths':[7,9,11],'initial_items_per_depth':5,'two_draws':True,'max_calls':50,'items':public,'audit':'Reject operations equal to either operand on observed values. Require a longest structural path where perturbing every operation output by either +1 or -1 individually changes the final answer. This local sensitivity check is not a proof against all algebraic shortcuts.','provenance':'New diagnostic items generated with upstream arithmetic generator; not sealed benchmark items; do not include in NCRI.'},indent=2)+'\n')
    return items

def readrows():
    p=OUT/'hard_rows.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

def run(selected):
    rows=readrows()
    if any(not r['valid'] for r in rows):raise SystemExit('STOP: existing no-CoT failure; no further purchases')
    validation_path=OUT/'hard_recipe_validation.jsonl'
    probe_count=len(validation_path.read_text().splitlines()) if validation_path.exists() else 0
    done={(r['problem_number'],r['draw']) for r in rows}
    for draw in [1,2]:
        for item in selected:
            if (item['problem_number'],draw) in done:continue
            if len(rows)+probe_count>=50:raise SystemExit('50-call cap reached')
            rec,raw=request('arithmetic',item)
            rec.update(draw=draw,structural_depth=item['structural_depth'],expression_sha256=item['expression_sha256'],stage='hard_extension')
            with (PRIV/'hard_responses.jsonl').open('a') as f:f.write(json.dumps({'problem_number':item['problem_number'],'draw':draw,'response':raw})+'\n')
            with (OUT/'hard_rows.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
            rows.append(rec)
            print(json.dumps({k:rec[k] for k in ['problem_number','draw','structural_depth','reasoning_tokens','valid','correct']}),flush=True)
            if not rec['valid']:raise SystemExit('STOP: no-CoT check failed; no further purchases')

def summarize():
    rows=readrows();table={}
    for depth in sorted({r['structural_depth'] for r in rows}):
        rr=[r for r in rows if r['structural_depth']==depth]
        table[str(depth)]={'n_items':len({r['problem_number'] for r in rr}),'responses':len(rr),'correct':sum(r['correct'] for r in rr),'accuracy':sum(r['correct'] for r in rr)/len(rr),'draws':{str(d):{'n':sum(r['draw']==d for r in rr),'correct':sum(r['draw']==d and r['correct'] for r in rr)} for d in [1,2]}}
    report={'model':MODEL,'calls':len(rows),'table':table,'invalid':sum(not r['valid'] for r in rows),'reasoning_tokens':sum(r['reasoning_tokens'] or 0 for r in rows),'usage':{k:sum(r['usage'].get(k,0) or 0 for r in rows) for k in ['input_tokens','output_tokens']},'scope':'New sensitivity-filtered arithmetic diagnostics, separate from the sealed benchmark and Neel\'s cross-task normalized depth estimate.'}
    repairpath=OUT/'hard_recipe_validation.jsonl'
    repairs=[json.loads(l) for l in repairpath.read_text().splitlines()] if repairpath.exists() else []
    allrows=rows+repairs
    report['initial_recipe_table']=report.pop('table')
    report['calls']=len(allrows)
    report['usage']={k:sum(r['usage'].get(k,0) or 0 for r in allrows) for k in ['input_tokens','output_tokens']}
    report['invalid']=sum(not r['valid'] for r in allrows)
    report['reasoning_tokens']=sum(r['reasoning_tokens'] or 0 for r in allrows)
    report['attempts']=[{'recipe':r.get('recipe','original'), 'problem_number':r['problem_number'], 'structural_depth':r['structural_depth'], 'reasoning_tokens':r['reasoning_tokens'], 'valid':r['valid'], 'answer_correct_after_reasoning':r['answer_correct']} for r in allrows]
    report['status']='halted_no_cot_validation_failed' if any(not r['valid'] for r in allrows) else 'in_progress_or_complete'
    report['threshold_estimate']=None
    report['conclusion']='Two recipes failed the no-CoT check on the first depth-7 item. No accuracy curve or 50% depth threshold was measured. This is a protocol limitation, not a measured reasoning-capacity limit.'
    (OUT/'hard_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','initial','summary']);a=ap.parse_args()
    if a.stage=='prepare':
        items=prepare();print('Frozen and audited',len(items),'items; no inference calls')
    elif a.stage=='initial':
        items=prepare();selected=[i for i in items if i['structural_depth'] in [7,9,11] and int(i['problem_number'].rsplit('-',1)[1])<=5];run(selected);summarize()
    else:summarize()
