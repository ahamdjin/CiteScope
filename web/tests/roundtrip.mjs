import {writeFileSync} from "node:fs";
import {auditAnswer, makeBenchmark} from "../audit-core.mjs";
const sources=[{id:1,url:"https://example.org/ref",text:"Zapier supports multi-step workflows with multiple actions."}];
const answer="Zapier supports multi-step workflows [1].";
const audit=auditAnswer(answer,sources);
const payload=makeBenchmark({
  name:"Synthetic browser-to-Python contract fixture",
  caseId:"browser-contract-01",
  query:"Does Zapier support multi-step workflows?",
  model:"synthetic-browser-test",
  runId:"r1",
  reviewer:"synthetic-test-reviewer",
  answer
},audit,{c1:{verdict:"supported",evidenceSourceId:"1",evidenceQuote:"supports multi-step workflows"}});
const path=process.argv[2];
if(!path) throw new Error("Output path required");
writeFileSync(path,JSON.stringify(payload,null,2)+"\n");
