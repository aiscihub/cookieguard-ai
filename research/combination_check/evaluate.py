#!/usr/bin/env python3
import hashlib, json, random
from pathlib import Path
from collections import defaultdict
import joblib, numpy as np, onnxruntime as ort

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent; TEST=HERE/'test'; DEV=HERE/'development'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,v):
    if p.exists(): raise RuntimeError(f'refusing to overwrite {p}')
    p.write_text(json.dumps(v,indent=2)+'\n')
def rows():
    out=[]
    for p in sorted((TEST/'batches').glob('rows-*.jsonl')): out += [json.loads(x) for x in p.read_text().splitlines() if x]
    return out
def session(path): return ort.InferenceSession(str(path),providers=['CPUExecutionProvider'])
def outputs(s,x): return dict(zip([o.name for o in s.get_outputs()],s.run(None,{'features':x})))
def rule_x(item,p):
    order=['authentication','tracking','preference','other']; labels=order
    return [p,*[item['raw'][k] for k in order],*[float(item['type']==k) for k in labels],item['context']['f_third_party_context'],item['context']['has_httponly'],item['context']['is_session_cookie']]

if not (TEST/'manifest.json').exists(): raise RuntimeError('test not frozen')
for line in (DEV/'locks.txt').read_text().splitlines():
    digest,name=line.split('  ',1)
    if sha((DEV/name).resolve())!=digest: raise RuntimeError(f'development lock changed: {name}')
data=rows(); manifest=json.loads((TEST/'manifest.json').read_text())
if len(data)!=manifest['records'] or len({x['normalizedName'] for x in data})!=manifest['normalizedNames']: raise RuntimeError('manifest mismatch')
if len({x['label'] for x in data})!=2 or manifest['normalizedNames']<300: raise RuntimeError('minimum clean test not met')
rules=[json.loads(x) for x in (TEST/'rule_scores.jsonl').read_text().splitlines() if x]
if len(rules)!=len(data) or [x['rowIndex'] for x in rules]!=list(range(len(data))): raise RuntimeError('rule alignment failed')
write_json(TEST/'evaluation_opened.json',{
    'openedAfterFreeze':True,
    'manifestSha256':sha(TEST/'manifest.json'),
    'selectionSha256':sha(DEV/'selection.json')
})
x=np.asarray([r['features'] for r in data],np.float32)
v3=np.asarray(outputs(session(ROOT/'waicy_2026/accuracy_push/model/main.onnx'),x)['probabilities'])[:,1]
v1all=np.asarray(outputs(session(ROOT/'extension-standalone/model/cookieguard_model.onnx'),x)['probabilities']); v1=v1all[:,3]; v1pred=np.argmax(v1all,axis=1)==3
k5=joblib.load(DEV/'k5.joblib'); k5x=np.asarray([rule_x(rule,p) for rule,p in zip(rules,v3)],np.float64); k5p=k5.predict_proba(k5x)[:,1]
val=json.loads((DEV/'validation_results.json').read_text()); thresholds={k:v['threshold'] for k,v in val['candidates'].items()}
pred=[]
for i,(row,rule,p) in enumerate(zip(data,rules,v3)):
    r=rule['type']=='tracking'; q=rule['normalized']['tracking']; k2=r or p>=thresholds['K2']['t']; k3=(r and p>=thresholds['K3']['tLow']) or ((not r) and p>=thresholds['K3']['tHigh']); k4=(p+q)/2>=thresholds['K4']['t']; k5d=k5p[i]>=thresholds['K5']['t']
    pred.append({'rowIndex':i,'label':row['label'],'normalizedName':row['normalizedName'],'siteId':row['siteId'],'name':row['name'],
      'scores':{'K0':float(p),'K1':float(q),'K2':float(max(p,float(r))),'K3':float(p-(thresholds['K3']['tLow'] if r else thresholds['K3']['tHigh'])),'K4':float((p+q)/2),'K5':float(k5p[i]),'v1':float(v1[i]),'everythingTracker':1.0},
      'decisions':{'K0':bool(p>=.4),'K1':r,'K2':bool(k2),'K3':bool(k3),'K4':bool(k4),'K5':bool(k5d),'v1':bool(v1pred[i]),'everythingTracker':True},'agreement':bool((p>=.4)==r)})
path=TEST/'predictions.jsonl'
if path.exists(): raise RuntimeError('predictions already exist')
path.write_text(''.join(json.dumps(x)+'\n' for x in pred))
groups=defaultdict(list)
for i,row in enumerate(data): groups[row['normalizedName']].append(i)
rng=random.Random(2026111106); nb=[rng.choice(groups[name]) for name in sorted(groups)]
write_json(TEST/'evaluation_completed.json',{'predictionsSha256':sha(path)})
write_json(TEST/'nb_selection.json',{'seed':2026111106,'indices':nb,'normalizedNames':[data[i]['normalizedName'] for i in nb]})
print(json.dumps({'rows':len(data),'names':len(groups),'N-B':len(nb),'selected':val['selected'],'predictionsSha256':sha(path)},indent=2))
