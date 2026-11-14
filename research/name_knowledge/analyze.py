#!/usr/bin/env python3
"""Regenerate results from frozen artifacts without inference or external calls."""
import hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent; TEST=HERE/'test'; CLOUD=HERE/'cloud'
rows=[]
for path in sorted((TEST/'batches').glob('rows-*.jsonl')): rows += [json.loads(x) for x in path.read_text().splitlines() if x]
pred=[json.loads(x) for x in (TEST/'predictions.jsonl').read_text().splitlines() if x]
if len(rows)!=len(pred): raise RuntimeError('prediction alignment failed')
for i,(row,item) in enumerate(zip(rows,pred)):
 if item['rowIndex']!=i or item['label']!=row['label'] or item['siteId']!=row['siteId']: raise RuntimeError('prediction identity mismatch')
methods=['selectedN','K0','K1','v1','everythingTracker']; metric_names=['balancedAccuracy','precision','recall']
def metrics(indices,method):
 y=np.asarray([bool(rows[i]['label']) for i in indices]); d=np.asarray([pred[i]['decisions'][method] for i in indices]); tn=int(np.sum(~y&~d));fp=int(np.sum(~y&d));fn=int(np.sum(y&~d));tp=int(np.sum(y&d));pos=tp+fn;neg=tn+fp
 return {'accuracy':(tp+tn)/len(indices) if indices else None,'balancedAccuracy':(tp/pos+tn/neg)/2 if pos and neg else None,'precision':tp/(tp+fp) if tp+fp else 0.0,'recall':tp/pos if pos else None,'confusion':{'tn':tn,'fp':fp,'fn':fn,'tp':tp}}
def summarize_view(name,indices,seed,unit):
 groups=defaultdict(list)
 if unit=='site':
  for i in indices: groups[rows[i]['siteId']].append(i)
 else:
  for i in indices: groups[str(i)].append(i)
 keys=sorted(groups); rng=np.random.default_rng(seed); samples={m:{k:[] for k in metric_names} for m in methods}; diffs={r:{k:[] for k in metric_names} for r in ['K0','K1']}; valid=0; rejected=0
 while valid<1000 and valid+rejected<10000:
  chosen=rng.integers(0,len(keys),len(keys)); draw=[i for j in chosen for i in groups[keys[j]]]
  if len({rows[i]['label'] for i in draw})<2: rejected+=1; continue
  vals={m:metrics(draw,m) for m in methods}; valid+=1
  for m in methods:
   for k in metric_names: samples[m][k].append(vals[m][k])
  for ref in diffs:
   for k in metric_names: diffs[ref][k].append(vals['selectedN'][k]-vals[ref][k])
 result={m:metrics(indices,m) for m in methods}
 for m in methods:
  for k in metric_names: result[m][k+'Ci95']=[float(x) for x in np.percentile(samples[m][k],[2.5,97.5])] if samples[m][k] else None
 paired={ref:{k:{'value':result['selectedN'][k]-result[ref][k] if result['selectedN'][k] is not None and result[ref][k] is not None else None,'ci95':[float(x) for x in np.percentile(diffs[ref][k],[2.5,97.5])] if diffs[ref][k] else None} for k in metric_names} for ref in diffs}
 hits=Counter('miss' if pred[i]['dictionary'] is None else pred[i]['dictionary']['source']+'_'+pred[i]['dictionary']['matchType'] for i in indices)
 return {'rows':len(indices),'normalizedNames':len({rows[i]['normalizedName'] for i in indices}),'sites':len({rows[i]['siteId'] for i in indices}),'tracker':sum(rows[i]['label'] for i in indices),'notTracker':sum(not rows[i]['label'] for i in indices),'dictionaryCounts':dict(sorted(hits.items())),'methods':result,'pairedSelectedNMinus':paired,'bootstrap':{'seed':seed,'unit':unit,'valid':valid,'rejected':rejected}}
all_idx=list(range(len(rows))); mb=json.loads((TEST/'mb_selection.json').read_text())['indices']; unseen=[i for i in all_idx if pred[i]['dictionary'] is None]; known=[i for i in all_idx if pred[i]['dictionary'] is not None]
views={'M-A':summarize_view('M-A',all_idx,2026111204,'site'),'M-B':summarize_view('M-B',mb,2026111205,'row'),'M-U':summarize_view('M-U',unseen,2026111206,'site'),'M-K':summarize_view('M-K',known,2026111207,'site')}
source_stats={}
for kind in ['D1_raw','D1_normalized','D2_exact','D2_wildcard']:
 idx=[i for i in all_idx if pred[i]['dictionary'] and pred[i]['dictionary']['source']+'_'+pred[i]['dictionary']['matchType']==kind]
 if idx:
  source_stats[kind]={'rows':len(idx),'rate':len(idx)/len(rows),'accuracy':sum(int(bool(pred[i]['dictionary']['label'])==bool(rows[i]['label'])) for i in idx)/len(idx),'confusion':metrics(idx,'selectedN')['confusion']}
 else: source_stats[kind]={'rows':0,'rate':0,'accuracy':None,'confusion':None}
def cases(mode):
 counts=Counter()
 for i in all_idx:
  cg=pred[i]['decisions']['selectedN']; k0=pred[i]['decisions']['K0']; truth=bool(rows[i]['label'])
  if (mode=='fixed' and cg==truth and k0!=truth) or (mode=='wrong' and cg!=truth): counts[rows[i]['normalizedName']]+=1
 output=[]
 for name,count in sorted(counts.items(),key=lambda x:(-x[1],x[0]))[:10]:
  i=next(j for j in all_idx if rows[j]['normalizedName']==name and pred[j]['dictionary'] is not None) if any(rows[j]['normalizedName']==name and pred[j]['dictionary'] is not None for j in all_idx) else next(j for j in all_idx if rows[j]['normalizedName']==name)
  output.append({'normalizedName':name,'rows':count,'dictionary':pred[i]['dictionary']})
 return output
manifest=json.loads((TEST/'manifest.json').read_text()); selection=json.loads((HERE/'development/selection.json').read_text()); d1=json.loads((HERE/'dictionary/d1_deployment.json').read_text()); d2=json.loads((HERE/'dictionary/d2.json').read_text()); timing=json.loads((HERE/'local_timing.json').read_text()); cloud=json.loads((CLOUD/'cloud_results.json').read_text())
result={'schemaVersion':1,'outcome':{'naturalMixImproved':views['M-A']['methods']['selectedN']['balancedAccuracy']>views['M-A']['methods']['K0']['balancedAccuracy'],'selected':selection['selected']},'crawl':manifest,'views':views,'dictionary':{'overallHitRows':len(known),'overallHitRate':len(known)/len(rows),'missRows':len(unseen),'sourceStats':source_stats,'d1SourceRows':d1['sourceRows'],'d1Ties':{'raw':len(d1['ties']['raw']),'normalized':len(d1['ties']['normalized'])},'d2Conflicts':{'exact':len(d2['conflicts']['exact']),'wildcard':len(d2['conflicts']['wildcard'])}},'selection':selection,'cases':{'dictionaryFixedModelErrors':cases('fixed'),'selectedNStillWrong':cases('wrong')},'cloud':cloud,'timing':timing,'integrity':{'analysisInputsOnly':True,'bootstrapSeeds':[2026111204,2026111205,2026111206,2026111207,2026111208]}}
(HERE/'results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
def pct(x): return 'undefined' if x is None else f'{100*x:.1f}%'
def estimate(m,key):
 ci=m.get(key+'Ci95'); return pct(m.get(key)) if not ci else f"{pct(m[key])} [{pct(ci[0])}, {pct(ci[1])}]"
ma=views['M-A']; full=cloud['fullSample']; us=cloud['unseenSubset']; cloud_better=any(full['methods'][m]['balancedAccuracy']>full['methods']['CookieGuard']['balancedAccuracy'] for m in ['cloudRun1','cloudRun2','cloudRun3','cloudMajority']) or (us.get('rows',0)>0 and any(us['methods'][m]['balancedAccuracy']>us['methods']['CookieGuard']['balancedAccuracy'] for m in ['cloudRun1','cloudRun2','cloudRun3','cloudMajority'] if us['methods'][m]['balancedAccuracy'] is not None))
opening=(f"On the natural-frequency M-A mix, CookieGuard reached {pct(ma['methods']['selectedN']['accuracy'])} accuracy and {pct(ma['methods']['selectedN']['balancedAccuracy'])} balanced accuracy, versus {pct(ma['methods']['K0']['balancedAccuracy'])} for model-only K0. "+("Cloud AI was more accurate on at least one identical-row comparison; " if cloud_better else "Cloud AI was not more accurate on the identical-row comparisons; ")+"the cloud result is a separate name-balanced 300-row M-B sample, not an M-A estimate. The deletion test remains the separate proof of the login cookie.")
lines=['# CookieGuard name knowledge: frozen study results','',opening,'','## 1. Outcome','',f"The frozen selected method was **{selection['selected']}**. It {'improved' if result['outcome']['naturalMixImproved'] else 'did not improve'} balanced accuracy over model-only K0 on M-A. The known-name layer hit {len(known):,}/{len(rows):,} rows ({pct(len(known)/len(rows))}); {len(unseen):,} rows were unseen.",'','## 2. Same-row cloud comparison','',f"On the {full['rows']}-row name-balanced sample, CookieGuard balanced accuracy was {pct(full['methods']['CookieGuard']['balancedAccuracy'])}; cloud runs 1–3 were "+', '.join(pct(full['methods'][f'cloudRun{x}']['balancedAccuracy']) for x in range(1,4))+f", and majority was {pct(full['methods']['cloudMajority']['balancedAccuracy'])}. The fixed unseen subset contained {us['rows']} rows; CookieGuard was {pct(us['methods'].get('CookieGuard',{}).get('balancedAccuracy'))} and cloud majority was {pct(us['methods'].get('cloudMajority',{}).get('balancedAccuracy'))}.",'',"Cloud AI reads cookie names and domains and can use general web knowledge. CookieGuard’s known-name layer uses only its own labeled data and the Apache-2.0 Open Cookie Database; its model sees cookie attributes and a third-party flag but no domain identity. CookieGuard can feed the later run-time deletion test; description-only cloud classification cannot prove the login cookie. Cloud prompts went to OpenAI; local CookieGuard used no network. Saved CLI metadata did not expose cost."]
lines += ['','| Slice | Method | Balanced accuracy [95%] | Precision [95%] | Recall [95%] | TN / FP / FN / TP |','|---|---|---:|---:|---:|---|']
for slice_name,slice_data in [('Full M-B sample',full),('Sample M-U',us)]:
 for method in ['CookieGuard','cloudRun1','cloudRun2','cloudRun3','cloudMajority']:
  m=slice_data['methods'].get(method)
  if not m: continue
  c=m['confusion']; lines.append(f"| {slice_name} | {method} | {estimate(m,'balancedAccuracy')} | {estimate(m,'precision')} | {estimate(m,'recall')} | {c['tn']} / {c['fp']} / {c['fn']} / {c['tp']} |")
lines += ['',f"Cloud-majority minus CookieGuard balanced accuracy was {pct(full['pairedCloudMinusCookieGuard']['cloudMajority']['balancedAccuracy']['value'])} [{pct(full['pairedCloudMinusCookieGuard']['cloudMajority']['balancedAccuracy']['ci95'][0])}, {pct(full['pairedCloudMinusCookieGuard']['cloudMajority']['balancedAccuracy']['ci95'][1])}] on the full sample"+(f" and {pct(us['pairedCloudMinusCookieGuard']['cloudMajority']['balancedAccuracy']['value'])} [{pct(us['pairedCloudMinusCookieGuard']['cloudMajority']['balancedAccuracy']['ci95'][0])}, {pct(us['pairedCloudMinusCookieGuard']['cloudMajority']['balancedAccuracy']['ci95'][1])}] on its M-U subset." if us.get('rows') else '.')]
lines += ['','## 3. Crawl and populations','',f"The crawl attempted {manifest['attemptedRanks']:,} ranks ({manifest['acceptedAttempts']:,} accepted attempts), found {manifest['usableSites']:,} usable Cookiebot/OneTrust sites, retained {manifest['records']:,} rows and {manifest['normalizedNames']:,} normalized names, and stopped because `{manifest['stopReason']}`. Restarts: {manifest['restarts']}. Discarded sites: {manifest['discardedSites']}.",'', '| View | Rows | Names | Sites | Tracker | Not tracker |','|---|---:|---:|---:|---:|---:|']
for name,v in views.items(): lines.append(f"| {name} | {v['rows']:,} | {v['normalizedNames']:,} | {v['sites']:,} | {v['tracker']:,} | {v['notTracker']:,} |")
lines += ['','## 4. Local accuracy','','| View | Method | Accuracy | Balanced accuracy | Precision | Recall | TN / FP / FN / TP |','|---|---|---:|---:|---:|---:|---|']
for view,v in views.items():
 for method in methods:
  m=v['methods'][method]; c=m['confusion']; lines.append(f"| {view} | {method} | {pct(m['accuracy'])} | {estimate(m,'balancedAccuracy')} | {estimate(m,'precision')} | {estimate(m,'recall')} | {c['tn']} / {c['fp']} / {c['fn']} / {c['tp']} |")
lines += ['','All intervals and paired selected-N differences are saved in `results.json`; M-A/M-U/M-K resample sites and M-B resamples name rows, with 1,000 valid draws.','', '## 5. Dictionary and selection','',f"D1 used {d1['sourceRows']:,} permitted CookieGuard rows. D2 is the Apache-2.0 Open Cookie Database at commit `7786335566460016f07a50705a92fc781c976f6f`. Selection used {selection['rows']} frozen 2026 development rows: N1 {pct(selection['methods']['N1']['balancedAccuracy'])}, N2 {pct(selection['methods']['N2']['balancedAccuracy'])}, N3 {pct(selection['methods']['N3']['balancedAccuracy'])}; tie set: {', '.join(selection['tieSet'])}. The select-side rows were excluded from Selection D1.",'', '| First hit | Rows | Hit rate | Label accuracy |','|---|---:|---:|---:|']
for name,s in source_stats.items(): lines.append(f"| {name} | {s['rows']:,} | {pct(s['rate'])} | {pct(s['accuracy'])} |")
lines += ['','## 6. Timing and privacy','',f"The complete N1 path averaged {timing['summaries']['warmBatch']['meanPerCookieMs']:.3f} ms/cookie in warm 11-cookie batches. Startup-inclusive mean was {timing['summaries']['startupInclusive']['meanMs']:.1f} ms/process. End-to-end scoring of the frozen cloud sample averaged {timing['sampleEndToEnd']['meanPerCookieMs']:.3f} ms/cookie. Cloud averaged {cloud['timing']['meanSecondsPerCookie']:.2f} seconds/cookie. Local timing made no network requests.",'', 'Incremental value scans covered crawl and local artifacts within the active restart scope. Prompts were admitted by exact structural rendering (A1); replies were admitted as exact Boolean objects (A2). Replies were not value-scanned because the cloud received no values.','', '## 7. Cases','', 'Most common normalized names where N1 corrected a K0 error:']
for x in result['cases']['dictionaryFixedModelErrors']: lines.append(f"- `{x['normalizedName']}` — {x['rows']} rows; {x['dictionary']['source']+' '+x['dictionary']['matchType'] if x['dictionary'] else 'miss'}")
lines += ['','Most common normalized names N1 still got wrong:']
for x in result['cases']['selectedNStillWrong']: lines.append(f"- `{x['normalizedName']}` — {x['rows']} rows; {x['dictionary']['source']+' '+x['dictionary']['matchType'] if x['dictionary'] else 'miss'}")
lines += ['','## 8. Limitations','', '- Consent-banner declarations can be noisy or conflicting.','- Only Cookiebot and OneTrust sites are represented.','- D1 includes 2026 development labels in the deployment/test condition.','- OCD categories are a third party’s judgment.','- The cloud comparison is a name-balanced 300-row sample, not the all-row M-A population.','- Tracker classification is not login-cookie identification.','', 'Stopped before §13: no product, model, demo, showcase, movie, or submission files were changed.']
(HERE/'results.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'resultsSha256':hashlib.sha256((HERE/'results.json').read_bytes()).hexdigest(),'reportSha256':hashlib.sha256((HERE/'results.md').read_bytes()).hexdigest()}))
