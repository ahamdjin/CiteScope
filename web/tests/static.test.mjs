import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync,existsSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {dirname,resolve} from "node:path";
const root=resolve(dirname(fileURLToPath(import.meta.url)),"..");
test("app entry and local modules exist",()=>{
  assert.ok(existsSync(resolve(root,"index.html")));
  assert.ok(existsSync(resolve(root,"app.mjs")));
  assert.ok(existsSync(resolve(root,"audit-core.mjs")));
  assert.ok(existsSync(resolve(root,"style.css")));
});
test("UI is keyboard-aware and labels its export truth limitations",()=>{
  const html=readFileSync(resolve(root,"index.html"),"utf8");
  assert.match(html,/id="answer"/);
  assert.match(html,/id="query"/);
  assert.match(html,/id="source-list"/);
  assert.match(html,/id="analyze-btn"/);
  assert.match(html,/id="json-btn"/);
  assert.match(html,/role="status"/);
  assert.match(html,/not independently validated/i);
});
test("no external scripts or background fetch",()=>{
  const html=readFileSync(resolve(root,"index.html"),"utf8");
  const js=readFileSync(resolve(root,"app.mjs"),"utf8");
  assert.doesNotMatch(html,/<script[^>]+src="https?:/);
  assert.doesNotMatch(js,/\bfetch\s*\(/);
  assert.doesNotMatch(js,/\blocalStorage\b|\bsessionStorage\b/);
});
