#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
from sklearn.metrics import balanced_accuracy_score,precision_score,recall_score,confusion_matrix
HERE=Path(__file__).resolve().parent; CLOUD=HERE/'cloud'
if not (HERE/'cloud_reply_privacy_pass.json').exists(): raise RuntimeError('cloud replies have not passed the privacy scan')
key=json.loads((CLOUD/'sample_key.json').read_text())['items']; ids=list(key); truth=np.asarray([key[x]['truth'] for x in ids],bool); cg=np.asarray([key[x]['cookieguard'] for x in ids],bool); meta=json.loads((CLOUD/'run_metadata.json').read_text())
validity={(x['batch'],x['run']):x['replyValid'] for x in meta['runs']}
def read(batch,run):
 if not validity.get((batch,run),False): return {}
 try:
  x=json.loads((CLOUD/'replies'/f'batch-{batch}-run-{run}.txt').read_text()); return x if isinstance(x,dict) else {}
 except: return {}
cloud={r:{} for r in range(1,4)}
for b in range(1,meta['batches']+1):
 batch=[x['id'] for x in json.loads((CLOUD/'sample_public.json').read_text())[(b-1)*50:b*50]]
 for r in cloud:
  reply=read(b,r)
  for x in batch: cloud[r][x]=reply.get(x) if isinstance(reply.get(x),bool) else None
def arr(mapping): return np.asarray([mapping[x] if isinstance(mapping.get(x),bool) else not key[x]['truth'] for x in ids],bool)
methods={f'cloudRun{r}':arr(cloud[r]) for r in cloud}; majority={}
for x in ids:
 vals=[cloud[r][x] for r in cloud if isinstance(cloud[r][x],bool)]; majority[x]=(sum(vals)>=2) if len(vals)>=2 else None
methods['cloudMajority']=arr(majority); methods['CookieGuard']=cg
METRICS=['balancedAccuracy','precision','recall']
def metrics(y,d):
 tn,fp,fn,tp=confusion_matrix(y,d,labels=[False,True]).ravel()
 return {'balancedAccuracy':float(balanced_accuracy_score(y,d)),'precision':float(precision_score(y,d,zero_division=0)),'recall':float(recall_score(y,d,zero_division=0)),'confusion':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}}
rng=np.random.default_rng(2026111111); samples={m:defaultdict(list) for m in methods}; diffs={m:defaultdict(list) for m in methods if m!='CookieGuard'}; valid=0
while valid<1000:
 idx=rng.integers(0,len(ids),len(ids))
 if len(set(truth[idx]))<2: continue
 vals={m:metrics(truth[idx],d[idx]) for m,d in methods.items()}; valid+=1
 for m in methods:
  for k in METRICS: samples[m][k].append(vals[m][k])
 for m in diffs:
  for k in METRICS: diffs[m][k].append(vals[m][k]-vals['CookieGuard'][k])
out={'schemaVersion':1,'sampleNames':len(ids),'methods':{},'pairedDifferencesCloudMinusCookieGuard':{},'invalidPolicy':'missing or non-Boolean answer counted wrong; no repair'}
for m,d in methods.items():
 out['methods'][m]=metrics(truth,d)
 for k in METRICS: out['methods'][m][k+'Ci95']=[float(x) for x in np.percentile(samples[m][k],[2.5,97.5])]
for m in diffs: out['pairedDifferencesCloudMinusCookieGuard'][m]={k:{'value':out['methods'][m][k]-out['methods']['CookieGuard'][k],'ci95':[float(x) for x in np.percentile(v,[2.5,97.5])]} for k,v in diffs[m].items()}
elapsed=[x['elapsedSeconds'] for x in meta['runs']]; out['timing']={'cloudMeanSecondsPerBatch':float(np.mean(elapsed)),'cloudMeanSecondsPerCookie':float(np.mean(elapsed)/50),'cloudMinSecondsPerCookie':min(elapsed)/50,'cloudMaxSecondsPerCookie':max(elapsed)/50}; out['validReplies']=sum(x['replyValid'] for x in meta['runs']);out['replyFiles']=len(meta['runs'])
(CLOUD/'cloud_results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
