#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent; CLOUD=HERE/'cloud'; public=json.loads((CLOUD/'sample_public.json').read_text()); manifest=json.loads((CLOUD/'sample_manifest.json').read_text())
intro='You are classifying browser cookies. For each item, decide whether it is a tracking cookie: analytics or advertising. Values and website names are withheld. The domain shown is the cookie domain. Reply with one JSON object whose keys are the IDs and whose values are true or false, e.g. {"C001": true, "C002": false}. Include every ID exactly once, with no prose, markdown, missing IDs, or extra IDs.\n\n'
checks=[]
for batch in range(1,manifest['batches']+1):
 rows=public[(batch-1)*50:batch*50]; lines=[intro]
 for x in rows:
  life='session' if x['lifetimeDays'] is None else f"{x['lifetimeDays']:.6g} days"
  lines.append(f"{x['id']} name={json.dumps(x['name'])}; domain={json.dumps(x['domain'])}; third-party={'yes' if x['thirdParty'] else 'no'}; Secure={'yes' if x['secure'] else 'no'}; HttpOnly={'yes' if x['httpOnly'] else 'no'}; SameSite={x['sameSite']}; lifetime={life}; value length={x['valueShape']['length']}; character set={x['valueShape']['characterSet']}\n")
 expected=''.join(lines).encode(); path=CLOUD/'prompts'/f'batch-{batch}.txt'; actual=path.read_bytes()
 if actual!=expected or hashlib.sha256(actual).hexdigest()!=manifest['prompts'][batch-1]['sha256']: raise RuntimeError(f'prompt {batch} structural mismatch')
 checks.append({'batch':batch,'rows':len(rows),'exact':True,'sha256':hashlib.sha256(actual).hexdigest()})
receipt={'schemaVersion':1,'amendment':'A1','passed':True,'basis':'exact fixed-template rendering of frozen structured rows','dataBeyondFrozenRows':False,'batches':checks}
(CLOUD/'prompt_structure_check.json').write_text(json.dumps(receipt,indent=2)+'\n'); (HERE/'cloud_prompt_privacy_pass.json').write_text(json.dumps({'schemaVersion':1,'passed':True,'basis':'structural A1','valueScanPerformed':False,'reason':'Prompts contain only frozen public fields and no cookie values.'},indent=2)+'\n'); print(json.dumps(receipt,indent=2))
