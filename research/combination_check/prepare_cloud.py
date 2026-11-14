#!/usr/bin/env python3
import hashlib,json,random
from pathlib import Path
HERE=Path(__file__).resolve().parent; TEST=HERE/'test'; CLOUD=HERE/'cloud'; CLOUD.mkdir(exist_ok=True); (CLOUD/'prompts').mkdir(exist_ok=True)
if any(CLOUD.iterdir()) and any((CLOUD/'prompts').iterdir()): raise RuntimeError('cloud sample already prepared')
rows=[]
for p in sorted((TEST/'batches').glob('rows-*.jsonl')): rows += [json.loads(x) for x in p.read_text().splitlines() if x]
pred=[json.loads(x) for x in (TEST/'predictions.jsonl').read_text().splitlines() if x]; nb=json.loads((TEST/'nb_selection.json').read_text())['indices']
chosen=random.Random(2026111109).sample(nb,300) if len(nb)>=300 else nb
ids=[f'C{i:03d}' for i in range(1,len(chosen)+1)]; random.Random(2026111110).shuffle(ids)
public=[]; key={'schemaVersion':1,'sampleSeed':2026111109,'idSeed':2026111110,'testManifestSha256':hashlib.sha256((TEST/'manifest.json').read_bytes()).hexdigest(),'items':{}}
for opaque,index in zip(ids,chosen):
 r=rows[index]; item={'id':opaque,'name':r['name'],'domain':r['domain'],'thirdParty':bool(r['features'][35]),'secure':r['secure'],'httpOnly':r['httpOnly'],'sameSite':r['sameSite'],'lifetimeDays':None if r['lifetimeSeconds'] is None else r['lifetimeSeconds']/86400,'valueShape':r['valueShape']}; public.append(item)
 key['items'][opaque]={'rowIndex':index,'normalizedName':r['normalizedName'],'truth':bool(r['label']),'cookieguard':pred[index]['decisions']['K3'],'cookieguardScore':pred[index]['scores']['K3']}
(CLOUD/'sample_public.json').write_text(json.dumps(public,indent=2)+'\n'); (CLOUD/'sample_key.json').write_text(json.dumps(key,indent=2)+'\n')
intro='You are classifying browser cookies. For each item, decide whether it is a tracking cookie: analytics or advertising. Values and website names are withheld. The domain shown is the cookie domain. Reply with one JSON object whose keys are the IDs and whose values are true or false, e.g. {"C001": true, "C002": false}. Include every ID exactly once, with no prose, markdown, missing IDs, or extra IDs.\n\n'
for batch,start in enumerate(range(0,len(public),50),1):
 lines=[intro]
 for x in public[start:start+50]:
  life='session' if x['lifetimeDays'] is None else f"{x['lifetimeDays']:.6g} days"
  lines.append(f"{x['id']} name={json.dumps(x['name'])}; domain={json.dumps(x['domain'])}; third-party={'yes' if x['thirdParty'] else 'no'}; Secure={'yes' if x['secure'] else 'no'}; HttpOnly={'yes' if x['httpOnly'] else 'no'}; SameSite={x['sameSite']}; lifetime={life}; value length={x['valueShape']['length']}; character set={x['valueShape']['characterSet']}\n")
 (CLOUD/'prompts'/f'batch-{batch}.txt').write_text(''.join(lines))
manifest={'schemaVersion':1,'items':len(public),'batches':(len(public)+49)//50,'itemsPerBatch':50,'samplePublicSha256':hashlib.sha256((CLOUD/'sample_public.json').read_bytes()).hexdigest(),'sampleKeySha256':hashlib.sha256((CLOUD/'sample_key.json').read_bytes()).hexdigest(),'prompts':[{ 'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((CLOUD/'prompts').glob('*.txt'))]}
(CLOUD/'sample_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
(HERE/'cloud_prompt_scan_request.json').write_text(json.dumps({'schemaVersion':1,'sampleManifestSha256':hashlib.sha256((CLOUD/'sample_manifest.json').read_bytes()).hexdigest(),'requiredBeforeCloudCalls':True},indent=2)+'\n')
