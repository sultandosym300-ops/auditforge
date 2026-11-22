import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {prepareReleaseEvidence} from './prepare_release_evidence.mjs';
const root=fs.mkdtempSync(path.join(os.tmpdir(),'auditforge-evidence-'));
try{
 fs.mkdirSync(path.join(root,'web/public'),{recursive:true});
 assert.equal(prepareReleaseEvidence(root).bundle_verified,false);
 const source='a=1\n';fs.writeFileSync(path.join(root,'source.py'),source);
 const proof={format:'auditforge-release-evidence',ci_conclusion:'success',source_commit:'a'.repeat(40),source_sha256:{'source.py':createHash('sha256').update(source).digest('hex')}};
 const output=path.join(root,'web/public/release-evidence.json');
 fs.writeFileSync(output,JSON.stringify(proof));assert.equal(prepareReleaseEvidence(root).bundle_verified,true);
 fs.writeFileSync(path.join(root,'source.py'),'a=2\n');assert.throws(()=>prepareReleaseEvidence(root),/stale/);
 fs.writeFileSync(output,JSON.stringify({...proof,source_sha256:{'../outside.py':'0'.repeat(64)}}));assert.throws(()=>prepareReleaseEvidence(root),/missing/);
 console.log('Release evidence: absent is unverified; valid content verified; stale and escaped sources rejected.');
}finally{fs.rmSync(root,{recursive:true,force:true});}
