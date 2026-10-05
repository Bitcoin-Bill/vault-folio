// Run with Node 20+: tests offline JS syntax, shared catalog and v1 interoperability.
const fs = require('node:fs');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root,'browser-edition/index.html'),'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
const context=vm.createContext({crypto:webcrypto,TextEncoder,TextDecoder,Uint8Array,atob,btoa,
 window:{addEventListener(){}},setInterval(){},setTimeout(){},console});
for(const script of scripts) vm.runInContext(script.replace(/runGate\(\);\s*$/,''),context);
const python=process.env.PYTHON || 'python';
function py(code,input){
 const result=spawnSync(python,['-B','-c',code],{cwd:root,input:JSON.stringify(input),encoding:'utf8'});
 if(result.status!==0)throw Error(result.stderr);return JSON.parse(result.stdout);
}
(async()=>{
 const browserCatalog=vm.runInContext('JSON.stringify({profiles:PROFILES,fields:RECORD_FIELDS,extra:EXTRA_BACKUP_FIELDS,access:ACCESS_EXTRA,direct:ACCESS_DIRECT})',context);
 const pythonCatalog=py('import json; from folio_catalog import PROFILES,FIELDS,EXTRA_BACKUP_FIELDS,ACCESS_EXTRA,ACCESS_DIRECT; print(json.dumps(dict(profiles=PROFILES,fields=FIELDS,extra=EXTRA_BACKUP_FIELDS,access=ACCESS_EXTRA,direct=ACCESS_DIRECT)))',{});
 assert.deepEqual(JSON.parse(browserCatalog),pythonCatalog);
 const env=await vm.runInContext(`encryptPlan({...blankPlan(),lawyers:[{name:'Test counsel'}],backupRecords:[{hint:'Ask the trustee'}]},'test guide passphrase')`,context);
 const code="import json,sys,importlib.util; s=importlib.util.spec_from_file_location('folio','vault-folio.py'); m=importlib.util.module_from_spec(s);s.loader.exec_module(m); p=m.decrypt_plan(json.load(sys.stdin),'test guide passphrase'); print(json.dumps(m.encrypt_plan(p,'test guide passphrase')))";
 context.envelope=py(code,env);
 const restored=await vm.runInContext("decryptPlan(envelope,'test guide passphrase')",context);
 assert.equal(restored.lawyers[0].name,'Test counsel');assert.equal(restored.backupRecords[0].hint,'Ask the trustee');
 await assert.rejects(vm.runInContext("decryptPlan(envelope,'wrong')",context));
 assert.equal(vm.runInContext("STEPS.filter(x=>x.custom==='records').length",context),5);
 context.guide=JSON.parse(JSON.stringify(restored));
 context.guide.accessRecords=[{kind:'EntropyLab journal',mode:'Direct access details inside encrypted guide',directAccess:'journal-only-secret'}];
 context.guide.instructions=[{title:'Family custom step',action:'Call known trustee',stop:'Stop if labels differ'}];
 const before=JSON.stringify(context.guide);
 const hidden=vm.runInContext('JSON.stringify(beneficiarySteps(guide))',context);
 const shown=vm.runInContext('JSON.stringify(beneficiarySteps(guide,true))',context);
 assert(!hidden.includes('journal-only-secret'));assert(shown.includes('journal-only-secret'));
 assert(hidden.includes('Call known trustee'));assert.equal(JSON.stringify(context.guide),before);
 console.log('PASS: browser syntax, catalog parity, Python/browser v1 round trip, wrong passphrase, added sections');
})().catch(e=>{console.error(e);process.exitCode=1;});
