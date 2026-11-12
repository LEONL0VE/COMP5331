"""Reproducible robustness study; NumPy + project algorithms only.

Outputs every attempted case (including infeasible ones), JSON summary and SVG.
Perturbation tests are empirical checks, not substitutes for the certificate.
"""
import csv
import hashlib
import json
import platform
from pathlib import Path
import sys
import time
import numpy as np
from _common import ROOT
from density_explain import DBSCAN, ExDBSCAN
from density_explain.datasets import mock_blobs, mock_moons, mock_rings
from density_explain.robust import robust_explain, match_cluster


def main():
    output = ROOT / 'results' / 'robust'
    output.mkdir(parents=True, exist_ok=True)
    rows=[]; skipped=[]
    seeds=[7,19]
    for name, maker, eps, min_pts in [('blobs',mock_blobs,.4,5),('moons',mock_moons,.22,4),('rings',mock_rings,.3,4),('usgs',None,5000,10)]:
        for seed in seeds if maker else [7]:
            X=maker(seed) if maker else np.load(ROOT/'data/processed/usgs_southern_california_2024.npz')['X']
            model=DBSCAN(eps,min_pts).fit(X); ex=ExDBSCAN(model)
            grid=[(e,m,DBSCAN(e,m).fit(X)) for m in [min_pts-1,min_pts,min_pts+1] for e in [eps*.9,eps,eps*1.1]]
            # Fixed deterministic query indices spanning the snapshot, not cherry-picked successes.
            indices=np.linspace(0,len(X)-1,4,dtype=int)
            angles=np.linspace(0,2*np.pi,256,endpoint=False)
            errors=.2*eps*np.column_stack([np.cos(angles),np.sin(angles)])
            for index in indices:
                p=X[index]; reachable=set(model.memberships(p)[0]); targets=[c for c in model.result_.cluster_ids if c not in reachable]
                if not targets:
                    skipped.append(dict(dataset=name,seed=seed,index=int(index),reason='No non-reachable target cluster'))
                    continue
                target=min(targets,key=lambda c: np.linalg.norm(X[model.core_indices_[model.labels_[model.core_indices_]==c]]-p,axis=1).min())
                matched=[(f,match_cluster(model.labels_,f.labels_,target)) for _,_,f in grid]
                for fixed in [(),(1,)]:
                    old=ex.explain(point=p,target_cluster=target,k=1,immutable_features=fixed)
                    for fraction in [0,.1,.2,.4]:
                        rho=fraction*eps
                        for method in ['original','nudge','certified']:
                            start=time.perf_counter(); z=None; margin=None; distance=None
                            if method=='certified':
                                result=robust_explain(model,p,target,rho,fixed)
                                if result['status']=='ok':
                                    z=np.array(result['counterfactual']);margin=result['certified_radius'];distance=result['distance']
                            elif old.returned_k:
                                z=old.counterfactuals[0].copy();anchor=X[old.reference_indices[0]]
                                if method=='nudge':
                                    direction=anchor-z;direction[list(fixed)]=0;length=np.linalg.norm(direction)
                                    if length:z+=direction*min(rho/length,1)
                                margin=max(0.,eps-float(np.linalg.norm(z-anchor)));distance=float(np.linalg.norm(z-p))
                            elapsed=time.perf_counter()-start
                            row=dict(dataset=name,seed=seed,eps=eps,index=int(index),target=target,fixed='y' if fixed else 'none',rho_fraction=fraction,method=method,feasible=z is not None,distance=distance,certified_radius=margin,endpoint_x=None if z is None else float(z[0]),endpoint_y=None if z is None else float(z[1]),compute_seconds=elapsed,perturbation_pass=None,stability_pass=None,unresolved=sum(m['status']!='matched' for _,m in matched))
                            if z is not None:
                                row['perturbation_pass']=sum(target in c for c in model.memberships(z+errors,atol=1e-10*max(1,eps)))/len(errors)
                                row['stability_pass']=sum(m['status']=='matched' and m['cluster'] in f.memberships(z,atol=1e-10*max(1,f.eps))[0] for f,m in matched)/len(matched)
                                if method=='certified':
                                    assert margin+1e-10*max(1,eps)>=rho
                                    probes=z+errors*(margin/(.2*eps))
                                    assert all(target in c for c in model.memberships(probes,atol=1e-10*max(1,eps)))
                                    assert all(z[j]==p[j] for j in fixed)
                            rows.append(row)
            print(name,seed,'complete',flush=True)
    with (output/'cases.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    groups=[]
    for method in ['original','nudge','certified']:
        for frac in [0,.1,.2,.4]:
            subset=[r for r in rows if r['method']==method and r['rho_fraction']==frac];valid=[r for r in subset if r['feasible']]
            groups.append(dict(method=method,rho_fraction=frac,attempted=len(subset),feasible=len(valid),perturbation_pass=float(np.mean([r['perturbation_pass'] for r in valid])) if valid else None,stability_pass=float(np.mean([r['stability_pass'] for r in valid])) if valid else None))
    paired=[]
    for frac in [0,.1,.2,.4]:
        records=[r for r in rows if r['rho_fraction']==frac]
        keys=set((r['dataset'],r['seed'],r['index'],r['fixed']) for r in records)
        triplets=[[r for r in records if (r['dataset'],r['seed'],r['index'],r['fixed'])==key] for key in sorted(keys)]
        common=[t for t in triplets if len(t)==3 and all(r['feasible'] for r in t)]
        for method in ['original','nudge','certified']:
            selected=[next(r for r in t if r['method']==method) for t in common]
            paired.append(dict(rho_fraction=frac,method=method,common_cases=len(common),mean_movement_over_eps=float(np.mean([r['distance']/r['eps'] for r in selected])),perturbation_pass=float(np.mean([r['perturbation_pass'] for r in selected])),stability_pass=float(np.mean([r['stability_pass'] for r in selected]))))
    fingerprints={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src/density_explain').glob('*.py'))}
    summary=dict(python=platform.python_version(),numpy=np.__version__,seeds=seeds,query_rule='Four evenly spaced observation indices; nearest non-reachable target cluster',perturbations='256 directions at radius 0.2 epsilon, same for every method; checks use 1e-10*max(1,eps) numerical tolerance',grid='epsilon x [0.9,1,1.1], MinPts +/-1; refit original snapshot; unresolved identities count as failures',timing='Diagnostic only: original explanation precomputed, therefore timings are not a method speed comparison',groups=groups,paired=paired,skipped_queries=skipped,source_sha256=fingerprints,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),usgs_sha256=hashlib.sha256((ROOT/'data/processed/usgs_southern_california_2024.npz').read_bytes()).hexdigest())
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    # A publication-exportable vector figure, no plotting dependency.
    colors={'original':'#d66b21','nudge':'#8265be','certified':'#087c72'}
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="440" viewBox="0 0 1000 440"><rect width="1000" height="440" fill="white"/><g font-family="sans-serif" fill="#193247"><text x="35" y="32" font-size="21">Robustness and parameter sensitivity</text><text x="35" y="55" font-size="12">Means over feasible cases; inspect summary.json for changing feasibility denominators.</text>']
    for panel,key,title in [(0,'perturbation_pass','Position perturbations (radius 0.2 ε)'),(1,'stability_pass','Nearby parameter grid')]:
        x0=65+panel*490;y0=325
        svg.append(f'<text x="{x0}" y="90" font-size="16">{title}</text>')
        for tick in [0,.25,.5,.75,1]:
            y=y0-210*tick;svg.append(f'<path d="M{x0} {y}h390" stroke="#dbe3e9"/><text x="{x0-35}" y="{y+4}" font-size="11">{tick:.2f}</text>')
        for method,color in colors.items():
            points=[]
            for g in groups:
                if g['method']==method and g[key] is not None:points.append(f"{x0+g['rho_fraction']/.4*390},{y0-g[key]*210}")
            svg.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3"/>')
        for fraction in [0,.1,.2,.4]:svg.append(f'<text x="{x0+fraction/.4*390-8}" y="350" font-size="12">{fraction}</text>')
        svg.append(f'<text x="{x0+100}" y="375" font-size="12">Requested tolerance / ε</text>')
    for j,(method,color) in enumerate(colors.items()):svg.append(f'<text x="{230+j*200}" y="415" font-size="14" fill="{color}">● {method}</text>')
    svg.append('</g></svg>');(output/'comparison.svg').write_text(''.join(svg))
    print(json.dumps(groups,indent=2))

if __name__=='__main__':main()
