#!/usr/bin/env python3
"""Offline structural-depth analysis. No network or model calls."""
import ast, collections, json, os, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parent
BENCH=pathlib.Path(os.environ.get('NOCOT_BENCH', str(ROOT.parent/'nocot-bench')))
sys.path.insert(0,str(BENCH))
from nocot.grade import load_bank

def structural_depth(node):
    if isinstance(node, ast.BinOp):
        return 1+max(structural_depth(node.left),structural_depth(node.right))
    if isinstance(node, ast.UnaryOp):
        return structural_depth(node.operand)
    if isinstance(node, ast.Constant) and isinstance(node.value,int):
        return 0
    raise ValueError('Unsupported expression node: '+type(node).__name__)

def main():
    _,items=load_bank('arithmetic',str(BENCH/'data'))
    bank={str(i['problem_number']):i for i in items}
    records=[json.loads(l) for l in (ROOT/'results/rows.jsonl').read_text().splitlines()]
    rows=[r for r in records if r['stage']=='main' and r['bank']=='arithmetic']
    groups=collections.defaultdict(list); item_depths=[]
    for row in rows:
        item=bank[str(row['problem_number'])]
        expression=item['problem'].split('Evaluate this Python expression. ',1)[1]
        node=ast.parse(expression,mode='eval').body
        depth=structural_depth(node)
        groups[depth].append(row)
        if row['draw']==1:
            item_depths.append({'problem_number':row['problem_number'],'binary_operator_count':sum(isinstance(n,ast.BinOp) for n in ast.walk(node)),'structural_depth':depth})
    table=[]
    for d,rr in sorted(groups.items()):
        table.append({'structural_depth':d,'unique_items':len({str(r['problem_number']) for r in rr}),'draws':{str(draw):{'correct':sum(r['correct'] for r in rr if r['draw']==draw),'n':sum(r['draw']==draw for r in rr)} for draw in [1,2]}})
    mean_input=sum(r['usage']['input_tokens'] for r in rows)/len(rows)
    mean_output=sum(r['usage']['output_tokens'] for r in rows)/len(rows)
    result={'method':'Longest path through binary-operation nodes in the expression AST; numeric signs do not count as arithmetic steps.','limitations':['Structural depth is not shortcut-aware effective depth. Algebraic simplifications and integer floor/modulo can erase dependencies.','This is not a reconstruction of Neel Nanda\'s perturbation-based, cross-task normalized 7.2-step estimate.','Only three distinct items have structural depth 6, the maximum sampled; no well-supported 50% crossing is observed.','Two draws of the same item are not independent new problems.'], 'table':table,'items':item_depths,'existing_average_input_tokens':mean_input,'existing_average_output_tokens':mean_output,'new_model_calls':0,
        'proposed_followup':{'status':'not run; pending budget review','initial_calls':30,'max_additional_calls':20,'max_total_calls':50,'initial_design':'Five new, nondegenerate problems at each of three verified dependent depths, two draws each. Nominal targets 7, 9, 11; audit actual dependency sensitivity locally before inference.','expansion_rule':'Use at most ten further unique problems, two draws each, to bracket/refine the transition. Report unresolved if the cap is reached; do not extrapolate a precise threshold.','input_token_planning_estimate':'About 55,000–95,000 tokens across 30–50 calls, based on the existing ~1,748 input tokens/call with allowance for longer questions. Not a hard input-token bound.','expected_output_tokens_if_no_cot':'About 360–600, using the existing ~12 output tokens/call.','max_output_tokens_per_call':300,'max_total_output_tokens':15000,'notes':['Reusing canonical demonstrations preserves comparability but dominates input cost.','Select/sensitivity-audit items locally and token-count exact requests before paid execution.','A single-task threshold is a cheaper diagnostic; reproducing the headline normalized metric needs multiple serial task families.','No dollar estimate without verified Fable 5.2 account pricing.']}}
    out=ROOT/'results/depth_analysis.json';out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'table':table,'new_model_calls':0,'output':str(out)},indent=2))
if __name__=='__main__': main()
