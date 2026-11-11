#!/usr/bin/env python3
"""Offline paired comparison. Does not call a model or publish any raw answers."""
import collections,json,math,pathlib,random
ROOT=pathlib.Path(__file__).resolve().parent

def ident(r):return (r['bank'],str(r['problem_number']))
def cell(r):return (r['family'],r['bank'])
def stats(pairs):
 n=len(pairs);fc=sum(f['correct'] for f,a in pairs);ac=sum(a['correct'] for f,a in pairs)
 fonly=sum(f['correct'] and not a['correct'] for f,a in pairs);aonly=sum(a['correct'] and not f['correct'] for f,a in pairs)
 discord=fonly+aonly
 p=min(1,2*sum(math.comb(discord,k) for k in range(min(fonly,aonly)+1))/2**discord) if discord else 1
 return {'n_pairs':n,'fable_correct':fc,'astra_correct':ac,'fable_accuracy':fc/n if n else None,'astra_accuracy':ac/n if n else None,'fable_minus_astra':(fc-ac)/n if n else None,'fable_only_correct':fonly,'astra_only_correct':aonly,'exploratory_exact_mcnemar_p':p}

def main():
 rows=[json.loads(l) for l in (ROOT/'results/matched_rows.jsonl').read_text().splitlines()]
 ff=[r for r in rows if r['phase']=='main'];aa=json.loads((ROOT/'results/matched_astra.json').read_text())['rows'];lookup={ident(r):r for r in aa}
 cells={}
 for c in sorted({cell(r) for r in aa}):
  f=[r for r in ff if cell(r)==c];a=[r for r in aa if cell(r)==c]
  def quality(rr):
   measured=[r for r in rr if not r['missing']]
   inv=sum(not r['valid'] for r in measured)
   return {'attempts':len(rr),'scorable':len(measured),'invalid':inv,'missing':len(rr)-len(measured),'invalid_fraction':inv/len(measured) if measured else None,'missing_fraction':1-len(measured)/len(rr) if rr else None}
  fq,aq=quality(f),quality(a)
  qualified=bool(f) and fq['invalid_fraction'] is not None and aq['invalid_fraction'] is not None and fq['invalid_fraction']<=.2 and aq['invalid_fraction']<=.2 and fq['missing_fraction']<=.2 and aq['missing_fraction']<=.2
  cells['/'.join(c)]={'fable_pooled_draw_quality':fq,'astra_quality':aq,'qualified':qualified}
 report={'cell_quality':cells,'draws':{},'notes':['One fixed published Astra draw per item. Fable draw2 is a repeat, not an independent second set of problems.','All-matched-scorable results are operational no-CoT success scores and can include cells with excessive reasoning failures.','Qualified-cell results exclude a source-bank cell if >20% of scorable replies are invalid, or >20% of attempts are missing, for either model. Fable quality is assessed across both draws to use one common inclusion set.','Missingness cutoff is an additional conservative comparison guard, not an assertion that Neel applied the identical missingness rule.','McNemar tests are exploratory, conditional on this fixed selected item set and published Astra realization; they do not establish overall model rankings.','Astra and Fable have different serving routes and model-specific suppression recipes; same questions and grader improve comparability but do not reproduce normalized 7.2-step calibration.']}
 for draw in [1,2]:
  pairs=[]
  for f in ff:
   if f['draw']!=draw:continue
   a=lookup[ident(f)]
   if not f['missing'] and not a['missing']:pairs.append((f,a))
  qualified=[(f,a) for f,a in pairs if cells['/'.join(cell(f))]['qualified']]
  report['draws'][str(draw)]={'all_matched_scorable':stats(pairs),'qualified_cells_only':stats(qualified),'by_family':{family:stats([(f,a) for f,a in pairs if f['family']==family]) for family in ['arithmetic','brew','chain','cfgpatch']}}
 (ROOT/'results/matched_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'draws':report['draws'],'qualified_cells':sum(v['qualified'] for v in cells.values()),'total_cells':len(cells)},indent=2))
if __name__=='__main__':main()
