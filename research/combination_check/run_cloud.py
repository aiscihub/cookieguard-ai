#!/usr/bin/env python3
import concurrent.futures,datetime as dt,hashlib,json,subprocess,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent; CLOUD=HERE/'cloud'; REPLIES=CLOUD/'replies'; REPLIES.mkdir(exist_ok=True)
if not (HERE/'cloud_prompt_privacy_pass.json').exists(): raise RuntimeError('cloud prompt privacy preflight has not passed')
CODEX=Path('/Users/zhenli/.vscode/extensions/openai.chatgpt-26.51021.22027-darwin-arm64/bin/macos-aarch64/codex')
manifest=json.loads((CLOUD/'sample_manifest.json').read_text()); public=json.loads((CLOUD/'sample_public.json').read_text())
if any(REPLIES.glob('*.txt')): raise RuntimeError('cloud replies already exist')
def sha(b): return hashlib.sha256(b).hexdigest()
def one(pair):
 batch,run=pair; prompt=(CLOUD/'prompts'/f'batch-{batch}.txt').read_bytes(); work=Path(tempfile.mkdtemp(prefix=f'combination-cloud-b{batch}-r{run}-',dir='/private/tmp')); reply_temp=Path(str(work)+'.reply.txt')
 command=[str(CODEX),'--no-daemon','-a','never','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--color','never','--json','-m','gpt-6-astra','-c','model_reasoning_effort="max"','-c','project_doc_max_bytes=0','-c','web_search="disabled"','--enable','skip_host_skill_discovery','--disable','apps','--disable','plugins','--disable','hooks','--disable','memories','--disable','multi_agent','--disable','shell_tool','--disable','unified_exec','--disable','browser_use','--disable','browser_use_external','--disable','computer_use','--disable','image_generation','--disable','shell_snapshot','--disable','view_image','--disable','sleep_tool','-C',str(work),'-o',str(reply_temp),'-']
 started=dt.datetime.now(dt.timezone.utc); before=time.perf_counter(); completed=subprocess.run(command,input=prompt,stdout=subprocess.PIPE,stderr=subprocess.PIPE); elapsed=time.perf_counter()-before; reply=reply_temp.read_bytes() if reply_temp.exists() else b''; (REPLIES/f'batch-{batch}-run-{run}.txt').write_bytes(reply)
 ids={x['id'] for x in public[(batch-1)*50:batch*50]}; valid=False
 try:
  parsed=json.loads(reply); valid=isinstance(parsed,dict) and set(parsed)==ids and all(isinstance(v,bool) for v in parsed.values())
 except Exception: pass
 return {'batch':batch,'run':run,'exitCode':completed.returncode,'startedAtUtc':started.isoformat(),'elapsedSeconds':elapsed,'cwd':str(work),'cwdEmptyAtStart':True,'promptSha256':sha(prompt),'replySha256':sha(reply),'replyBytes':len(reply),'replyValid':valid,'stderr':completed.stderr.decode('utf8','replace')[-4000:]}
jobs=[(b,r) for b in range(1,manifest['batches']+1) for r in range(1,4)]; before=time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: runs=list(pool.map(one,jobs))
meta={'schemaVersion':1,'datePacific':'2026-11-11','timezone':'America/Los_Angeles','interface':'Codex CLI fresh ephemeral sessions','model':'gpt-6-astra','reasoningEffort':'max','batches':manifest['batches'],'runsPerBatch':3,'isolatedSessions':len(jobs),'method':{'emptyWorkingDirectoryPerSession':True,'toolsMemoryWebOff':True,'repliesSavedBeforeScoring':True,'replyAdmission':'structural (Amendment A2)','invalidReplyPolicy':'all 50 IDs count wrong'},'runs':sorted(runs,key=lambda x:(x['batch'],x['run'])),'elapsedSeconds':time.perf_counter()-before}
(CLOUD/'run_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
reply_admission={'schemaVersion':1,'passed':True,'basis':'structural (Amendment A2)','replyFiles':len(runs),'validReplies':sum(x['replyValid'] for x in runs),'invalidReplies':sum(not x['replyValid'] for x in runs),'valueScanPerformed':False,'reason':'The cloud received no cookie values; exact 50-ID Boolean-object validity is recorded per reply in run_metadata.json.'}
(HERE/'cloud_reply_privacy_pass.json').write_text(json.dumps(reply_admission,indent=2)+'\n')
print(json.dumps({'runs':len(runs),'valid':sum(x['replyValid'] for x in runs),'elapsedSeconds':meta['elapsedSeconds']}))
