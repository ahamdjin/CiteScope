/**
 * CiteScope Evidence Review — browser-side deterministic checks.
 * No remote calls, LLM requests, telemetry or browser storage.
 * This is annotation support, NOT an automatic factuality oracle.
 */

const CITE_PATTERN = /\[((?:\d+\s*,\s*)*\d+)\]/g;
const QUOTE_PATTERN = /["“]([^"”]+)["”]/g;
const VERDICTS = new Set([
  "unreviewed", "supported", "partially_supported", "unsupported", "contradicted"
]);

export function citationIds(text) {
  const found = [];
  for (const match of String(text).matchAll(CITE_PATTERN)) {
    for (const id of match[1].split(",")) found.push(String(Number(id.trim())));
  }
  return found;
}

export function normalize(text) {
  return String(text).replace(/\s+/g, " ").trim().toLocaleLowerCase("en-US");
}

export function segmentAnswer(text) {
  return String(text).replace(/\r\n?/g, "\n")
    .split(/(?<=[.!?])\s+(?=\S)|\n+/u)
    .map(part => part.trim()).filter(Boolean);
}

export function validateSources(sources) {
  if (!Array.isArray(sources) || sources.length < 1) {
    throw new Error("Add at least one source.");
  }
  const seen = new Set();
  return sources.map((source, index) => {
    if (!source || typeof source !== "object") throw new Error("Source must be an object.");
    const idValue = String(source.id ?? "").trim();
    if (!/^\d+$/.test(idValue) || !Number.isSafeInteger(Number(idValue)) || Number(idValue) < 1) {
      throw new Error("Source " + (index + 1) + " needs a positive numeric ID.");
    }
    const id = String(Number(idValue));
    if (seen.has(id)) throw new Error("Source IDs must be unique.");
    seen.add(id);
    const body = source.text;
    if (typeof body !== "string" || !body.trim()) {
      throw new Error("Paste source text for [" + id + "].");
    }
    const url = String(source.url || "").trim();
    if (url && !/^https?:\/\/\S+$/i.test(url)) {
      throw new Error("Source [" + id + "] URL must start with https:// or http://.");
    }
    return {id: Number(id), text: body.trim(), ...(url ? {url} : {})};
  });
}

export function auditAnswer(answer, rawSources) {
  if (typeof answer !== "string" || !answer.trim()) {
    throw new Error("Paste an AI answer to review.");
  }
  const sources = validateSources(rawSources);
  const byId = new Map(sources.map(source => [String(source.id), source]));
  const sentences = segmentAnswer(answer);
  const units = [];
  const quotes = [];
  let resolvable = 0;
  let mentions = 0;
  for (const [index, text] of sentences.entries()) {
    const refs = [...new Set(citationIds(text))];
    const cited = citationIds(text);
    mentions += cited.length;
    resolvable += cited.filter(id => byId.has(id)).length;
    const unknown = refs.filter(id => !byId.has(id));
    const matches = [];
    for (const match of text.matchAll(QUOTE_PATTERN)) {
      const quote = match[1].trim();
      if (normalize(quote).length < 8) continue;
      const validIds = refs.filter(id => byId.has(id));
      const matching = validIds.filter(id => normalize(byId.get(id).text).includes(normalize(quote)));
      let status = "not_found_in_cited_sources";
      if (!refs.length) status = "uncited";
      else if (!validIds.length) status = "unresolvable_citation";
      else if (matching.length) status = "matched_exact_text";
      const quoted = {quote, status, matched_source_ids: matching, claim_id: "c" + (index + 1)};
      matches.push(quoted);
      quotes.push(quoted);
    }
    units.push({
      id: "c" + (index + 1), text, citations: refs,
      unresolvable: unknown,
      claim: text.replace(CITE_PATTERN, "").trim(),
      quotations: matches
    });
  }
  return {
    sources,
    units,
    quotes,
    metrics: {
      claim_candidates: units.length,
      candidates_with_citations: units.filter(unit => unit.citations.length).length,
      cited_references: mentions,
      valid_references: resolvable,
      unknown_references: [...new Set(units.flatMap(unit => unit.unresolvable))],
      exact_quote_matches: quotes.filter(q => q.status === "matched_exact_text").length,
      quoted_passages: quotes.length,
      citation_resolvability: mentions ? resolvable / mentions : null,
      citation_coverage: units.length ? units.filter(u => u.citations.length).length / units.length : null,
    }
  };
}

export function validateReview(audit, reviews, reviewer) {
  const sourceById = new Map(audit.sources.map(source => [String(source.id), source]));
  const out = [];
  for (const unit of audit.units) {
    const review = reviews[unit.id] || {};
    const verdict = review.verdict || "unreviewed";
    if (!VERDICTS.has(verdict)) throw new Error("Invalid verdict for " + unit.id + ".");
    if (verdict !== "unreviewed" && !String(reviewer || "").trim()) {
      throw new Error("Enter your reviewer ID before exporting labeled claims.");
    }
    const citeId = String(review.evidenceSourceId || "").trim();
    const quote = String(review.evidenceQuote || "").trim();
    const evidence = [];
    if (citeId || quote) {
      if (!citeId || !quote) throw new Error(unit.id + ": choose an evidence source and paste an excerpt.");
      if (!unit.citations.includes(citeId)) {
        throw new Error(unit.id + ": evidence source must be cited by the claim.");
      }
      if (!sourceById.has(citeId)) throw new Error(unit.id + ": evidence source cannot be resolved.");
      if (!normalize(sourceById.get(citeId).text).includes(normalize(quote))) {
        throw new Error(unit.id + ": the evidence excerpt is not in the cited source snapshot.");
      }
      evidence.push({source_id: Number(citeId), quote});
    }
    if (verdict === "supported" && !evidence.length) {
      throw new Error(unit.id + ": supported claims require an exact evidence excerpt.");
    }
    const claim = {
      id: unit.id,
      text: unit.claim || unit.text,
      citations: unit.citations.map(Number),
      verdict,
      evidence,
    };
    if (verdict !== "unreviewed") claim.reviewer = String(reviewer).trim();
    out.push(claim);
  }
  return out;
}

export function makeBenchmark(details, audit, reviews) {
  for (const key of ["name", "caseId", "query", "model", "runId"]) {
    if (!String(details[key] || "").trim()) throw new Error("Provide " + key + ".");
  }
  const claims = validateReview(audit, reviews, details.reviewer);
  return {
    name: details.name.trim(),
    sample_type: "manual_review_single_case",
    label_provenance: "One local reviewer; not independently validated or adjudicated.",
    cases: [{
      id: details.caseId.trim(), query: details.query.trim(),
      sources: audit.sources,
      runs: [{
        model: details.model.trim(), run_id: details.runId.trim(),
        answer: details.answer, claims
      }]
    }]
  };
}

export function reviewSummary(claims, audit) {
  const reviewed = claims.filter(c => c.verdict !== "unreviewed");
  const supported = reviewed.filter(c => c.verdict === "supported");
  const citedReviewed = reviewed.filter(c => c.citations.length);
  const citedSupported = supported.filter(c => c.citations.length);
  return {
    candidates: claims.length,
    reviewed: reviewed.length,
    supported: supported.length,
    contradicted: reviewed.filter(c => c.verdict === "contradicted").length,
    unreviewed: claims.length - reviewed.length,
    cited_support_rate: citedReviewed.length ? citedSupported.length / citedReviewed.length : null,
    citation_resolvability: audit.metrics.citation_resolvability
  };
}

export function markdownReport(details, audit, claims) {
  const stats = reviewSummary(claims, audit);
  const pct = n => n === null ? "N/A" : (n * 100).toFixed(1) + "%";
  const heading = s => String(s).replace(/[\r\n]+/g, " ").replace(/[<>]/g, "");
  const lines = [
    "# CiteScope Evidence Review — " + heading(details.name),
    "",
    "Question: " + heading(details.query),
    "Model (self-reported): " + heading(details.model),
    "Reviewer: " + heading(details.reviewer || "Not provided"),
    "",
    "## Summary",
    "",
    "- Candidate claim units: " + stats.candidates,
    "- Human reviewed: " + stats.reviewed,
    "- Fully supported (reviewer labels): " + stats.supported,
    "- Contradicted (reviewer labels): " + stats.contradicted,
    "- Unresolved source IDs: " + (audit.metrics.unknown_references.join(", ") || "None"),
    "- Citation resolvability: " + pct(stats.citation_resolvability),
    "- Reviewed cited-claim support: " + pct(stats.cited_support_rate),
    "",
    "## Claim review",
    ""
  ];
  for (const claim of claims) {
    lines.push("### " + heading(claim.id) + " — " + heading(claim.verdict));
    lines.push("");
    lines.push(heading(claim.text));
    lines.push("");
    lines.push("Cited sources: " + (claim.citations.map(id => "[" + id + "]").join(", ") || "None"));
    if (claim.evidence.length) {
      lines.push("Evidence source: [" + claim.evidence[0].source_id + "]");
      lines.push("Evidence excerpt: " + heading(claim.evidence[0].quote));
    }
    lines.push("");
  }
  lines.push("## Limits", "", "All support verdicts were provided by a reviewer, not independently proven by CiteScope.", "A source ID existing or a quote matching text does not establish factual entailment.", "Sentence segmentation produces review candidates, not guaranteed atomic claims.");
  return lines.join("\n") + "\n";
}
