#!/usr/bin/env python3
"""Offline, descriptive logistic depth fits. Repeated draws are never pooled."""
import json,math,pathlib
ROOT=pathlib.Path(__file__).resolve().parent

def softplus(x):return x if x>30 else math.log1p(math.exp(x))
def fit(points):
    # p(correct|depth)=sigmoid(slope*(depth50-depth)); slope constrained positive.
    grid=[j/50 for j in range(2001)]
    slopes=[math.exp(math.log(.001)+j/200*math.log(20000)) for j in range(201)]
    profiles=[];best=(float('inf'),None,None)
    for midpoint in grid:
        likelihoods=[]
        for slope in slopes:
            loss=sum(k*softplus(-slope*(midpoint-d))+(n-k)*softplus(slope*(midpoint-d)) for d,k,n in points)
            likelihoods.append((loss,slope))
        loss,slope=min(likelihoods)
        profiles.append(loss)
        if loss<best[0]:best=(loss,midpoint,slope)
    included=[m for m,loss in zip(grid,profiles) if 2*(loss-best[0])<=3.841458820694124]
    return {'depth50':best[1],'slope':best[2],'nominal_profile95':[min(included),max(included)],'profile_interval_hits_grid_boundary':min(included)==grid[0] or max(included)==grid[-1],'unique_items_in_draw':sum(n for _,_,n in points),'counts':[{'depth':d,'correct':k,'n':n} for d,k,n in points]}

def main():
    rows=[json.loads(l) for l in (ROOT/'results/continuation_rows.jsonl').read_text().splitlines()]
    report={'model':'claude-fable-5-2','recipe':'strong_plain_hard10','depths_included':[4,5,6,7],'depths_excluded':{'9':'50% missing through truncation','11':'60% missing and >20% invalid among scorable rows'},'fits':{},'method':'Single-family logistic accuracy curve with zero chance floor. Primary score counts nontruncated reasoning as wrong and excludes truncated/blind responses. Fit each draw separately; do not double the sample size by pooling repeat answers.','limitations':['Five unique problems per depth; descriptive, highly uncertain estimate.','The nominal likelihood interval is conditional on this selected item set and adaptive depth selection; it does not include task-design, recipe-selection, or full serving uncertainty.','No chance-floor correction is used.','Dependent depth is structurally counted and locally +/-1 sensitivity-audited, not Neel\'s original cross-task normalized arithmetic-step units.','Cannot use these numbers for a direct 7.2-versus-Fable comparison.']}
    for draw in [1,2]:
        points=[]
        for depth in [4,5,6,7]:
            rr=[r for r in rows if r['phase']=='main' and r['draw']==draw and r['depth']==depth and not r['truncated'] and not r['blind']]
            points.append((depth,sum(r['correct'] for r in rr),len(rr)))
        report['fits'][str(draw)]=fit(points)
    (ROOT/'results/continuation_depth_fit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
