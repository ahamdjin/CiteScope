import {
  auditAnswer, makeBenchmark, markdownReport, validateReview, reviewSummary
} from "./audit-core.mjs";

const byId = id => document.getElementById(id);
const state = {audit:null, details:null, reviews:{}, reviewUnits:[], nextUnitId:0, snapshot:null};

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function feedback(message, error = false) {
  const node = byId("feedback");
  node.textContent = message || "";
  node.className = error ? "feedback error" : "feedback";
  if (error) node.scrollIntoView({behavior:"smooth", block:"nearest"});
}

function sourceCard(initial = {}) {
  const card = el("div", "source-card");
  const title = el("div", "source-title");
  title.append(el("span", "", "Source snapshot"), el("button", "source-remove", "Remove"));
  title.querySelector("button").type = "button";
  title.querySelector("button").addEventListener("click", () => {
    if (byId("source-list").children.length === 1) return feedback("Keep at least one source.", true);
    card.remove();
    feedback("");
  });
  const first = el("div", "source-meta");
  const idLabel = el("label", "field");
  idLabel.append(el("span", "", "Citation ID"));
  const idInput = el("input"); idInput.className = "source-id"; idInput.type = "number"; idInput.min = "1"; idInput.step = "1"; idInput.value = String(initial.id || 1);
  idLabel.append(idInput);
  const urlLabel = el("label", "field");
  urlLabel.append(el("span", "", "Source URL (optional)"));
  const urlInput = el("input"); urlInput.type = "url"; urlInput.className = "source-url"; urlInput.placeholder = "https://example.org/article"; urlInput.value = initial.url || "";
  urlLabel.append(urlInput); first.append(idLabel, urlLabel);
  const textLabel = el("label", "field");
  textLabel.append(el("span", "", "Source text / excerpt"));
  const textarea = el("textarea"); textarea.className = "source-body"; textarea.rows = 4; textarea.placeholder = "Paste the original source snapshot here"; textarea.value = initial.text || "";
  textLabel.append(textarea);
  card.append(title, first, textLabel);
  return card;
}

function nextSourceId() {
  const ids = [...byId("source-list").querySelectorAll(".source-id")].map(x => Number(x.value)).filter(Number.isSafeInteger);
  return Math.max(0, ...ids) + 1;
}

function addSource(source = {}) {
  byId("source-list").append(sourceCard({id: nextSourceId(), ...source}));
}

function readSources() {
  return [...byId("source-list").children].map(card => ({
    id: card.querySelector(".source-id").value,
    url: card.querySelector(".source-url").value,
    text: card.querySelector(".source-body").value,
  }));
}

function readDetails() {
  return {
    query: byId("query").value, answer: byId("answer").value,
    model: byId("model").value, caseId: byId("case-id").value,
    runId: "browser-review-001", name: byId("study-name").value,
    reviewer: byId("reviewer").value
  };
}

function inputSignature() {
  const {query, answer, model, caseId} = readDetails();
  return JSON.stringify({query,answer,model,caseId,sources:readSources()});
}

function stat(id, text) {byId(id).textContent = text;}

function renderStats() {
  const {audit,reviews} = state;
  if (!audit) return;
  const reviewed = Object.values(reviews).filter(r => r.verdict && r.verdict !== "unreviewed").length;
  stat("stat-claims", String(audit.metrics.claim_candidates));
  stat("stat-unknown", String(audit.metrics.unknown_references.length));
  stat("stat-resolved", audit.metrics.citation_resolvability === null ? "N/A" : (audit.metrics.citation_resolvability * 100).toFixed(0) + "%");
  stat("stat-reviewed", reviewed + " / " + state.reviewUnits.length);
}

function metricTag(value, kind = "neutral") {
  return el("span", "mini-tag " + kind, value);
}
function makeField(labelText, className, value, choices) {
  const wrapper = el("label", "field");
  wrapper.append(el("span", "", labelText));
  let control;
  if (choices) {
    control = el("select", className);
    choices.forEach(option => {
      const item = el("option", "", option.text);
      item.value = option.value;
      control.append(item);
    });
  } else {
    control = el("textarea", className);
    control.rows = 2;
    control.placeholder = "Paste an exact passage from the cited source";
  }
  control.value = value || "";
  wrapper.append(control);
  return {wrapper,control};
}

function renderClaims() {
  const {audit} = state;
  const area = byId("claim-list");
  area.replaceChildren();
  const existing = state.reviews;
  state.reviews = {};
  const validIDs = new Set(audit.sources.map(s => String(s.id)));
  for (const [unitIndex,unit] of state.reviewUnits.entries()) {
    const block = el("article", "claim-card");
    const top = el("div", "claim-top");
    const titleBar = el("div", "claim-identity");
    titleBar.append(el("span", "claim-id", unit.id.toUpperCase()));
    const splitButton = el("button", "split-button", "+ Split");
    splitButton.type = "button";
    splitButton.title = "Create another claim from this same sentence. Edit both to isolate factual assertions.";
    splitButton.addEventListener("click", () => {
      const duplicate = {...unit, id:"c" + (++state.nextUnitId)};
      state.reviewUnits.splice(unitIndex+1,0,duplicate);
      state.reviews[duplicate.id] = {verdict:"unreviewed",evidenceSourceId:"",evidenceQuote:"",claimText:duplicate.claim || duplicate.text};
      renderClaims();
      renderStats();
    });
    titleBar.append(splitButton);
    top.append(titleBar);
    const tags = el("div", "tag-row");
    if (unit.citations.length) {
      unit.citations.forEach(id => tags.append(metricTag("[" + id + "]", validIDs.has(id) ? "ok" : "error")));
    } else tags.append(metricTag("No citation", "warning"));
    top.append(tags);
    block.append(top, el("p", "claim-text", unit.claim || unit.text));
    if (unit.unresolvable.length) {
      block.append(el("p", "claim-warning", "Unknown cited source: " + unit.unresolvable.map(id => "[" + id + "]").join(", ")));
    }
    if (unit.quotations.length) {
      for (const quote of unit.quotations) {
        block.append(el("p", quote.status === "matched_exact_text" ? "quote-good" : "claim-warning",
          "Quoted passage: " + quote.status.replaceAll("_"," ") + " — “" + quote.quote + "”"));
      }
    }
    const row = el("div", "review-grid");
    const previous = existing[unit.id] || {};
    const claimEdit = makeField("Atomic claim (edit or split composite statements)", "claim-edit",
      previous.claimText ?? (unit.claim || unit.text));
    claimEdit.control.classList.add("atomic-edit");
    const verdict = makeField("Human verdict", "verdict-select", previous.verdict || "unreviewed", [
      {value:"unreviewed",text:"Not reviewed"},
      {value:"supported",text:"Fully supported"},
      {value:"partially_supported",text:"Partially supported"},
      {value:"unsupported",text:"Not supported"},
      {value:"contradicted",text:"Contradicted"}
    ]);
    const evidenceId = makeField("Evidence source", "evidence-select", previous.evidenceSourceId || "", [
      {value:"",text:"Select a cited source"},
      ...unit.citations.filter(id => validIDs.has(id)).map(id => ({value:id,text:"Source [" + id + "]"}))
    ]);
    const quote = makeField("Exact supporting / contradicting excerpt (optional, required for 'supported')", "quote-input", previous.evidenceQuote || "");
    const note = el("p", "review-hint", "Verdicts come from your judgment, not an automatic AI score. Examine context and qualifiers before labeling.");
    row.append(claimEdit.wrapper, verdict.wrapper, evidenceId.wrapper, quote.wrapper);
    block.append(row,note);
    area.append(block);
    state.reviews[unit.id] = {
      verdict:verdict.control.value,evidenceSourceId:evidenceId.control.value,
      evidenceQuote:quote.control.value,claimText:claimEdit.control.value
    };
    function update() {
      state.reviews[unit.id] = {
        verdict:verdict.control.value,
        evidenceSourceId:evidenceId.control.value,
        evidenceQuote:quote.control.value,claimText:claimEdit.control.value
      };
      renderStats();
    }
    verdict.control.addEventListener("change", update);
    evidenceId.control.addEventListener("change", update);
    quote.control.addEventListener("input", update);
    claimEdit.control.addEventListener("input", update);
  }
  byId("result-count").textContent = state.reviewUnits.length + " review claim(s)";
}

function renderAlerts() {
  const area = byId("alert-list");
  area.replaceChildren();
  const unknown = state.audit.metrics.unknown_references;
  if (unknown.length) {
    area.append(el("div", "alert warning", "Some references have no supplied source: " + unknown.map(x => "["+x+"]").join(", ") + "."));
  }
  const uncited = state.audit.units.filter(u => !u.citations.length);
  if (uncited.length) {
    area.append(el("div", "alert warning", uncited.length + " claim candidate(s) have no numbered citation. This does not mean they are false."));
  }
  const quoteMisses = state.audit.quotes.filter(q => q.status !== "matched_exact_text");
  if (quoteMisses.length) {
    area.append(el("div", "alert warning", quoteMisses.length + " literal quote check(s) need attention."));
  }
  if (!area.children.length) {
    area.append(el("div", "alert neutral", "All numbered references resolve and no obvious quotation mismatch was detected. Claim support still needs human review."));
  }
}

function analyze() {
  try {
    const details = readDetails();
    const audit = auditAnswer(details.answer, readSources());
    state.audit = audit;
    state.reviewUnits = audit.units.map(unit => ({...unit}));
    state.nextUnitId = audit.units.length;
    state.details = details;
    state.snapshot = inputSignature();
    state.reviews = {};
    renderClaims();
    renderAlerts();
    renderStats();
    byId("results").classList.remove("hidden");
    feedback("Structural checks completed. Review the claims below; evidence support is not automatically verified.");
    byId("results").scrollIntoView({behavior:"smooth",block:"start"});
  } catch (error) {feedback(error.message, true);}
}

function download(filename, body, mime) {
  const blob = new Blob([body], {type:mime});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function exportData(kind) {
  try {
    if (!state.audit) throw new Error("Inspect an answer first.");
    if (state.snapshot !== inputSignature()) {
      throw new Error("The answer or source inputs changed. Click Inspect citations again before exporting.");
    }
    const details = readDetails();
    const benchmark = makeBenchmark(details,{...state.audit,units:state.reviewUnits},state.reviews);
    const safe = details.caseId.trim().replace(/[^a-z0-9._-]+/gi,"-").slice(0,72) || "case";
    if (kind === "json") {
      download("citescope-" + safe + ".json", JSON.stringify(benchmark,null,2) + "\n", "application/json");
    } else {
      const claims = benchmark.cases[0].runs[0].claims;
      download("citescope-" + safe + ".md", markdownReport(details,state.audit,claims), "text/markdown");
    }
    feedback("Export created locally. No data was uploaded.");
  } catch (error) {feedback(error.message, true);}
}

function loadExample() {
  byId("query").value = "Is Zapier difficult to learn?";
  byId("answer").value = 'Zapier only supports single-step automations [1]. It has filters and branching paths [1]. n8n can connect external APIs using HTTP requests [2].';
  byId("model").value = "Illustrative example (not a real model result)";
  byId("case-id").value = "zapier-learning-demo";
  byId("study-name").value = "Automation Source Review — Demo";
  byId("reviewer").value = "";
  byId("source-list").replaceChildren();
  addSource({id:1,url:"https://example.org/zapier-reference",
    text:"Zapier supports multi-step workflows with multiple actions. Filters and branching Paths can control which actions run."});
  addSource({id:2,url:"https://example.org/n8n-reference",
    text:"n8n workflows can communicate with external APIs using HTTP Request nodes and API credentials."});
  state.audit = null; state.reviewUnits = []; state.reviews = {}; state.snapshot = null;
  byId("results").classList.add("hidden");
  ["stat-claims","stat-unknown","stat-resolved","stat-reviewed"].forEach(id => stat(id,"—"));
  feedback("Illustrative example loaded. These are synthetic source excerpts, not independently collected research.");
}

byId("add-source").addEventListener("click", () => addSource());
byId("analyze-btn").addEventListener("click", analyze);
byId("demo-btn").addEventListener("click", loadExample);
byId("json-btn").addEventListener("click", () => exportData("json"));
byId("md-btn").addEventListener("click", () => exportData("markdown"));
addSource({id:1});


// Resume an exported, single-case CiteScope review. Entirely local.
byId("import-btn").addEventListener("click", () => byId("import-file").click());
byId("import-file").addEventListener("change", async event => {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  try {
    if (file.size > 2_000_000) throw new Error("Choose a review file under 2 MB.");
    const payload = JSON.parse(await file.text());
    if (!Array.isArray(payload?.cases) || payload.cases.length !== 1 ||
        !Array.isArray(payload.cases[0].runs) || payload.cases[0].runs.length !== 1) {
      throw new Error("Import expects one CiteScope benchmark case with one run.");
    }
    const c = payload.cases[0], run = c.runs[0];
    if (!Array.isArray(run.claims) || !Array.isArray(c.sources) || typeof run.answer !== "string") {
      throw new Error("The import is missing sources, answer, or review claims.");
    }
    const audit = auditAnswer(run.answer,c.sources);
    const allAnswerRefs = new Set(audit.units.flatMap(u=>u.citations));
    const seen = new Set();
    const reviewUnits = run.claims.map(claim => {
      const id = String(claim.id);
      const refs = claim.citations.map(String);
      if(!id || seen.has(id) || typeof claim.text !== "string" || !claim.text.trim() ||
         refs.some(ref=>!allAnswerRefs.has(ref))) {
        throw new Error("Invalid or duplicate claims in imported review.");
      }
      seen.add(id);
      return {id,text:claim.text,claim:claim.text,citations:refs,
        unresolvable:refs.filter(ref=>!audit.sources.some(source=>String(source.id)===ref)),
        quotations:[]};
    });
    const prior = {};
    for (const claim of run.claims) {
      prior[String(claim.id)] = {
        verdict:claim.verdict || "unreviewed",
        claimText:claim.text,
        evidenceSourceId:claim.evidence?.[0]?.source_id == null ? "" : String(claim.evidence[0].source_id),
        evidenceQuote:claim.evidence?.[0]?.quote || ""
      };
    }
    byId("query").value = c.query;
    byId("answer").value = run.answer;
    byId("model").value = run.model;
    byId("case-id").value = c.id;
    byId("study-name").value = payload.name || "Imported CiteScope review";
    byId("reviewer").value = run.claims.find(claim=>claim.reviewer)?.reviewer || "";
    byId("source-list").replaceChildren();
    c.sources.forEach(source => addSource(source));
    state.audit = audit;
    state.details = readDetails();
    state.reviewUnits = reviewUnits;
    state.reviews = prior;
    state.nextUnitId = Math.max(0,audit.units.length,...reviewUnits.map(unit => /^c\d+$/.test(unit.id) ? Number(unit.id.slice(1)) : 0));
    state.snapshot = inputSignature();
    renderClaims();
    renderAlerts();
    renderStats();
    byId("results").classList.remove("hidden");
    feedback("Review imported. Labels were supplied in the file; CiteScope has not independently validated them.");
    byId("results").scrollIntoView({behavior:"smooth",block:"start"});
  } catch(error) {feedback("Import failed: " + error.message,true);}
});
