// Deletes e2e test data. Dry-run by default; pass --yes to delete.
// Usage: set -a; . ../.cloud.env; set +a; node scripts/cleanup_e2e.mjs [--yes]
import { createClient } from "../web/node_modules/@supabase/supabase-js/dist/index.mjs";
const yes = process.argv.includes("--yes");
const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
const must = (r) => { if (r.error) throw new Error(r.error.message); return r.data; };

const cit = must(await sb.from("citizens").select("id").like("full_name", "E2E %"));
const citIds = cit.map((x) => x.id);
const byData = must(await sb.from("cases").select("id").eq("data->>_e2e", "true"));
const byCit = citIds.length ? must(await sb.from("cases").select("id").in("citizen_id", citIds)) : [];
const caseIds = [...new Set([...byData, ...byCit].map((x) => x.id))];

async function listAll(prefix) { // recursive storage listing
  const out = []; const { data } = await sb.storage.from("case-files").list(prefix, { limit: 1000 });
  for (const o of data ?? []) { const p = `${prefix}/${o.name}`; if (o.id) out.push(p); else out.push(...await listAll(p)); }
  return out;
}
const paths = [];
for (const id of caseIds) paths.push(...await listAll(id));
const jobIds = caseIds.length ? must(await sb.from("automation_jobs").select("id").in("case_id", caseIds)).map((x) => x.id) : [];
const count = async (t, col, ids) => ids.length ? (await sb.from(t).select("id", { count: "exact", head: true }).in(col, ids)).count : 0;
const counts = { citizens: citIds.length, cases: caseIds.length, documents: await count("documents", "case_id", caseIds),
  consents: await count("consents", "case_id", caseIds), automation_jobs: jobIds.length, job_prompts: await count("job_prompts", "job_id", jobIds),
  case_events: caseIds.length ? (await sb.from("case_events").select("id", { count: "exact", head: true }).in("case_id", caseIds)).count : 0,
  storage_objects: paths.length };
console.log(yes ? "DELETING:" : "DRY RUN (use --yes to delete):", JSON.stringify(counts));
if (yes) {
  for (let i = 0; i < paths.length; i += 100) must(await sb.storage.from("case-files").remove(paths.slice(i, i + 100)));
  if (caseIds.length) must(await sb.from("cases").delete().in("id", caseIds)); // cascades to dependents
  if (citIds.length) must(await sb.from("citizens").delete().in("id", citIds));
  console.log("done");
}
