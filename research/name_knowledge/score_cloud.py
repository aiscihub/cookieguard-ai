#!/usr/bin/env python3
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent; CLOUD=HERE/'cloud'
key=json.loads((CLOUD/'sample_key.json').read_text())['items']; ids=list(key); meta=json.loads((CLOUD/'run_metadata.json').read_text()); public=json.loads((CLOUD/'sample_public.json').read_text())
valid={(x['batch'],x['run']):x['replyValid'] for x in meta['runs']}
cloud={run:{} for run in range(1,4)}
for batch in range(1,meta['batches']+1):
 batch_ids=[x['id'] for x in public[(batch-1)*50:batch*50]]
 for run in cloud:
  answer={}
  if valid.get((batch,run),False):
   try: answer=json.loads((CLOUD/'replies'/f'batch-{batch}-run-{run}.txt').read_text())
   except Exception: answer={}
  for opaque in batch_ids: cloud[run][opaque]=answer.get(opaque) if isinstance(answer.get(opaque),bool) else None

def decision(mapping, opaque):
 value=mapping.get(opaque); return value if isinstance(value,bool) else not key[opaque]['truth']
methods={f'cloudRun{run}':{opaque:decision(cloud[run],opaque) for opaque in ids} for run in cloud}
majority={}
for opaque in ids:
 vals=[decision(cloud[run],opaque) for run in cloud]
 majority[opaque]=sum(vals)>=2
methods['cloudMajority']=majority; methods['CookieGuard']={opaque:key[opaque]['cookieguard'] for opaque in ids}

def metric(subset, mapping):
 y=np.asarray([key[x]['truth'] for x in subset],bool); d=np.asarray([mapping[x] for x in subset],bool)
 tn=int(np.sum(~y&~d)); fp=int(np.sum(~y&d)); fn=int(np.sum(y&~d)); tp=int(np.sum(y&d)); pos=tp+fn; neg=tn+fp
 return {'balancedAccuracy':None if not pos or not neg else (tp/pos+tn/neg)/2,'precision':tp/(tp+fp) if tp+fp else 0.0,'recall':tp/pos if pos else None,'confusion':{'tn':tn,'fp':fp,'fn':fn,'tp':tp}}
def view(subset):
 base={name:metric(subset,mapping) for name,mapping in methods.items()}; rng=np.random.default_rng(2026111208); names=['balancedAccuracy','precision','recall']; samples={name:{k:[] for k in names} for name in methods}; diffs={name:{k:[] for k in names} for name in methods if name!='CookieGuard'}; valid_n=0; rejected=0
 while valid_n<1000 and valid_n+rejected<10000:
  indices=rng.integers(0,len(subset),len(subset)); drawn=[subset[i] for i in indices]; truth={key[x]['truth'] for x in drawn}
  if len(truth)<2: rejected+=1; continue
  values={name:metric(drawn,mapping) for name,mapping in methods.items()}; valid_n+=1
  for name in methods:
   for k in names: samples[name][k].append(values[name][k])
  for name in diffs:
   for k in names: diffs[name][k].append(values[name][k]-values['CookieGuard'][k])
 for name in methods:
  for k in names: base[name][k+'Ci95']=[float(x) for x in np.percentile(samples[name][k],[2.5,97.5])] if samples[name][k] else None
 paired={name:{k:{'value':base[name][k]-base['CookieGuard'][k],'ci95':[float(x) for x in np.percentile(diffs[name][k],[2.5,97.5])]} for k in names} for name in diffs} if base['CookieGuard']['balancedAccuracy'] is not None else {}
 return {'rows':len(subset),'tracker':sum(key[x]['truth'] for x in subset),'notTracker':sum(not key[x]['truth'] for x in subset),'methods':base,'pairedCloudMinusCookieGuard':paired,'bootstrap':{'seed':2026111208,'valid':valid_n,'rejected':rejected}}
unseen=[x for x in ids if key[x]['unseen']]; elapsed=[x['elapsedSeconds'] for x in meta['runs']]
out={'schemaVersion':1,'fullSample':view(ids),'unseenSubset':view(unseen) if unseen else {'rows':0,'methods':{}},'validReplies':sum(valid.values()),'replyFiles':len(valid),'timing':{'meanSecondsPerBatch':float(np.mean(elapsed)),'meanSecondsPerCookie':float(np.mean(elapsed)/50),'minimumSecondsPerCookie':float(min(elapsed)/50),'maximumSecondsPerCookie':float(max(elapsed)/50)},'invalidPolicy':'invalid whole reply counts every answer wrong; no retry or repair'}
(CLOUD/'cloud_results.json').write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps({'fullRows':len(ids),'unseenRows':len(unseen),'validReplies':out['validReplies']},indent=2))
