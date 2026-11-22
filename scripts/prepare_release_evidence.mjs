import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
export function prepareReleaseEvidence(root){
 const target=path.join(root,'web/public/release-evidence.json');
 const empty={format:'auditforge-release-evidence',version:1,bundle_verified:false,scope:'No exact-commit external CI evidence supplied for this build. Run the local checks or provide a verified release artifact.'};
 if(!fs.existsSync(target)){fs.writeFileSync(target,JSON.stringify(empty));return empty;}
 let evidence;try{evidence=JSON.parse(fs.readFileSync(target,'utf8'));}catch{throw Error('Malformed release evidence');}
 if(!evidence.source_commit){fs.writeFileSync(target,JSON.stringify(empty));return empty;}
 if(evidence.format!==empty.format||evidence.ci_conclusion!=='success'||!/^[0-9a-f]{40}$/.test(evidence.source_commit)||!Object.keys(evidence.source_sha256||{}).length)throw Error('Invalid release evidence');
 for(const [name,expected] of Object.entries(evidence.source_sha256)){
  const file=path.resolve(root,name);
  if(!file.startsWith(path.resolve(root)+path.sep)||!fs.existsSync(file))throw Error('Release source missing: '+name);
  const bytes=fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n');
  if(createHash('sha256').update(bytes).digest('hex')!==expected)throw Error('Release evidence is stale: '+name);
 }
 evidence.bundle_verified=true;fs.writeFileSync(target,JSON.stringify(evidence,null,2));return evidence;
}
