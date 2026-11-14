#!/usr/bin/env python3
import hashlib, json, random
from pathlib import Path

HERE=Path(__file__).resolve().parent; TEST=HERE/'test'; CLOUD=HERE/'cloud'
if CLOUD.exists(): raise RuntimeError('cloud directory already exists')
(CLOUD/'prompts').mkdir(parents=True)
rows=[]
for path in sorted((TEST/'batches').glob('rows-*.jsonl')): rows += [json.loads(x) for x in path.read_text().splitlines() if x]
pred=[json.loads(x) for x in (TEST/'predictions.jsonl').read_text().splitlines() if x]
mb=json.loads((TEST/'mb_selection.json').read_text())['indices']
chosen=random.Random(2026111202).sample(mb,300) if len(mb)>=300 else list(mb)
ids=[f'C{i:03d}' for i in range(1,len(chosen)+1)]; random.Random(2026111203).shuffle(ids)
public=[]; key={'schemaVersion':1,'sampleSeed':2026111202,'idSeed':2026111203,'items':{}}
for opaque,index in zip(ids,chosen):
 row=rows[index]; item={'id':opaque,'name':row['name'],'domain':row['domain'],'thirdParty':bool(row['features'][35]),'secure':row['secure'],'httpOnly':row['httpOnly'],'sameSite':row['sameSite'],'lifetimeDays':None if row['lifetimeSeconds'] is None else row['lifetimeSeconds']/86400,'valueShape':row['valueShape']}; public.append(item)
 key['items'][opaque]={'rowIndex':index,'normalizedName':row['normalizedName'],'truth':bool(row['label']),'unseen':pred[index]['dictionary'] is None,'cookieguard':pred[index]['decisions']['selectedN']}
(CLOUD/'sample_public.json').write_text(json.dumps(public,indent=2)+'\n'); (CLOUD/'sample_key.json').write_text(json.dumps(key,indent=2)+'\n')
intro='You are classifying browser cookies. For each item, decide whether it is a tracking cookie: analytics or advertising. Values and website names are withheld. The domain shown is the cookie domain. Reply with one JSON object whose keys are the IDs and whose values are true or false, e.g. {"C001": true, "C002": false}. Include every ID exactly once, with no prose, markdown, missing IDs, or extra IDs.\n\n'
for batch,start in enumerate(range(0,len(public),50),1):
 lines=[intro]
 for x in public[start:start+50]:
  life='session' if x['lifetimeDays'] is None else f"{x['lifetimeDays']:.6g} days"
  lines.append(f"{x['id']} name={json.dumps(x['name'])}; domain={json.dumps(x['domain'])}; third-party={'yes' if x['thirdParty'] else 'no'}; Secure={'yes' if x['secure'] else 'no'}; HttpOnly={'yes' if x['httpOnly'] else 'no'}; SameSite={x['sameSite']}; lifetime={life}; value length={x['valueShape']['length']}; character set={x['valueShape']['characterSet']}\n")
 (CLOUD/'prompts'/f'batch-{batch}.txt').write_text(''.join(lines))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest={'schemaVersion':1,'items':len(public),'batches':(len(public)+49)//50,'itemsPerBatch':50,'samplePublicSha256':sha(CLOUD/'sample_public.json'),'sampleKeySha256':sha(CLOUD/'sample_key.json'),'prompts':[{'file':p.name,'sha256':sha(p)} for p in sorted((CLOUD/'prompts').glob('*.txt'))]}
(CLOUD/'sample_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n'); print(json.dumps(manifest,indent=2))
