import {test} from "node:test";
import assert from "node:assert/strict";
import {
  auditAnswer, citationIds, validateSources, validateReview,
  makeBenchmark, reviewSummary, markdownReport
} from "../audit-core.mjs";

const sources = [
  {id:1,url:"https://example.org/a",text:"Zapier supports multi-step workflows and paths. The launch was in 2024."},
  {id:2,text:"n8n can integrate APIs using HTTP requests and credential authentication."}
];
const details = {
  name:"Automation Citation Review",caseId:"auto-01",query:"Is Zapier difficult?",
  model:"Demo AI",runId:"run-1", reviewer:"analyst-01",
  answer:"Zapier only allows one action [1]. n8n can use HTTP requests [2]."
};
test("handles standalone and grouped references",()=>{
  assert.deepEqual(citationIds("hello [1] and [2, 3]"),["1","2","3"]);
});
test("rejects invalid source records",()=>{
  assert.throws(()=>validateSources([{id:1,text:"hi"},{id:"1",text:"bye"}]),/unique/);
  assert.throws(()=>validateSources([{id:1,text:""}]),/Paste source text/);
  assert.throws(()=>validateSources([]),/at least one/);
});
test("valid citations and correct claims",()=>{
  const audit=auditAnswer(details.answer,sources);
  assert.equal(audit.units.length,2);
  assert.equal(audit.metrics.citation_resolvability,1);
  assert.deepEqual(audit.units[0].citations,["1"]);
});
test("unknown citations remain visible rather than being called false",()=>{
  const audit=auditAnswer("The launch was in 2024 [7].",sources);
  assert.deepEqual(audit.metrics.unknown_references,["7"]);
  assert.equal(audit.units[0].unresolvable[0],"7");
});
test("quotes must appear in cited source rather than any source",()=>{
  const yes=auditAnswer('Documentation says "multi-step workflows" [1].',sources);
  assert.equal(yes.quotes[0].status,"matched_exact_text");
  const no=auditAnswer('Documentation says "multi-step workflows" [2].',sources);
  assert.equal(no.quotes[0].status,"not_found_in_cited_sources");
});
test("manual supported verdict requires an exact evidence excerpt and reviewer",()=>{
  const audit=auditAnswer(details.answer,sources);
  assert.throws(()=>validateReview(audit,{c1:{verdict:"supported"}},details.reviewer),/require an exact/);
  assert.throws(()=>validateReview(audit,{c1:{verdict:"contradicted"}},""),/reviewer ID/);
  assert.throws(()=>validateReview(audit,{c1:{verdict:"supported",evidenceSourceId:"2",evidenceQuote:"multi-step workflows"}},details.reviewer),/must be cited/);
  assert.throws(()=>validateReview(audit,{c1:{verdict:"supported",evidenceSourceId:"1",evidenceQuote:"completely invented"}},details.reviewer),/not in the cited source/);
});
test("benchmark export conforms to CiteScope Python schema",()=>{
  const audit=auditAnswer(details.answer,sources);
  const reviews={
    c1:{verdict:"contradicted",evidenceSourceId:"1",evidenceQuote:"Zapier supports multi-step workflows"},
    c2:{verdict:"supported",evidenceSourceId:"2",evidenceQuote:"n8n can integrate APIs using HTTP requests"}
  };
  const result=makeBenchmark(details,audit,reviews);
  assert.equal(result.cases.length,1);
  assert.equal(result.cases[0].runs[0].claims[1].evidence[0].source_id,2);
  assert.equal(result.sample_type,"manual_review_single_case");
  const summary=reviewSummary(result.cases[0].runs[0].claims,audit);
  assert.equal(summary.reviewed,2);
  assert.equal(summary.cited_support_rate,0.5);
  assert.match(markdownReport(details,audit,result.cases[0].runs[0].claims),/not independently proven/);
});
test("an unreviewed session never invents support scores",()=>{
  const audit=auditAnswer(details.answer,sources);
  const result=makeBenchmark(details,audit,{});
  assert.equal(reviewSummary(result.cases[0].runs[0].claims,audit).cited_support_rate,null);
  assert.equal(result.cases[0].runs[0].claims[0].verdict,"unreviewed");
});
