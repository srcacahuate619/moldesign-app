// API-only MET-01 capsule. Reuses the QA environment without completing the worktree.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {spawn, execFileSync} from 'node:child_process';
const [repo, runtime, capsule, number, action='up'] = process.argv.slice(2);
if (![repo,runtime,capsule].every(path.isAbsolute)) throw Error('Absolute paths required');
const statePath=path.join(capsule,'private-session.json');
if (action==='down') {
  const s=JSON.parse(fs.readFileSync(statePath));
  try { process.kill(s.pid); } catch(e) { if(e.code!=='ESRCH') throw e; }
  console.log(JSON.stringify({stopped:s.pid}));
} else {
  if(fs.existsSync(statePath)) throw Error('New capsule required; do not overwrite evidence');
  const {entornoBackend,carpetasDe,puertosDe}=await import(pathToFileURL(path.join(repo,'scripts/qa_sandbox/lib.mjs')));
  const ports=puertosDe(Number(number)), dirs=carpetasDe(capsule);
  for(const d of Object.values(dirs)) fs.mkdirSync(d,{recursive:true});
  const secret=crypto.randomBytes(32).toString('hex');
  const env=entornoBackend({base:process.env,repoRoot:repo,runtimeRoot:runtime,capsula:capsule,puertos:ports,token:secret,vinaCpu:4});
  env.PYTHONDONTWRITEBYTECODE='1';
  env.VINA_EXECUTABLE_PATH=path.join(repo,'tools/vina/vina.exe');
  env.VINA_TEMP_DIR=dirs.tmp;
  // Prevent the scoring libraries from each claiming the whole CPU beside Vina.
  env.OMP_NUM_THREADS='1'; env.MKL_NUM_THREADS='1'; env.OPENBLAS_NUM_THREADS='1';
  const fd=fs.openSync(path.join(dirs.logs,'backend.log'),'a');
  const p=spawn(path.join(repo,'python-embed/python.exe'),['-m','uvicorn','api.main:app','--host','127.0.0.1','--port',String(ports.back),'--loop','asyncio','--app-dir',path.join(repo,'backend')],{cwd:path.join(repo,'backend'),env,detached:true,windowsHide:true,stdio:['ignore',fd,fd]});
  p.unref(); fs.closeSync(fd);
  fs.writeFileSync(statePath,JSON.stringify({pid:p.pid,secret,env,base:`http://127.0.0.1:${ports.back}`}));
  const publicState={pid:p.pid,ports,source_commit:execFileSync('git',['-C',repo,'rev-parse','HEAD'],{encoding:'utf8'}).trim(),started:new Date().toISOString(),api_only:true,frontend:false,bytecode_disabled:true,vina_cpu:4,qa_environment:'scripts/qa_sandbox/lib.mjs::entornoBackend',profile_isolated:true};
  fs.writeFileSync(path.join(capsule,'public-session.json'),JSON.stringify(publicState,null,2)+'\n');
  const limit=Date.now()+240000;
  for(;;) {
    try { const r=await fetch(`http://127.0.0.1:${ports.back}/health`,{signal:AbortSignal.timeout(5000)}); if(r.ok) break; } catch {}
    if(Date.now()>limit) {process.kill(p.pid);throw Error('Backend not healthy');}
    await new Promise(r=>setTimeout(r,500));
  }
  console.log(JSON.stringify(publicState));
}
