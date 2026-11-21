// Usage: set -a; . ../.cloud.env; set +a; node scripts/verify_crm.mjs
import { createClient } from "../web/node_modules/@supabase/supabase-js/dist/index.mjs";
const opt = { auth: { persistSession: false } };
const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY, opt);
const admin = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, opt);
let fails = 0; const ok = (n, c, d = "") => { console.log(`${c ? "PASS" : "FAIL"} ${n}${!c && d ? " - " + d : ""}`); if (!c) fails++; };
let caseId, path;
try {
  const s = await sb.auth.signInWithPassword({ email: process.env.CRM_TEST_EMAIL, password: process.env.CRM_TEST_PASSWORD });
  ok("sign in", !s.error, s.error?.message);
  const sv = await sb.from("services").select("id,fields").limit(50);
  ok("list services", !sv.error && sv.data.length > 0, sv.error?.message);
  const cz = await sb.from("citizens").select("id").limit(1);
  const c = await sb.from("cases").insert({ citizen_id: cz.data?.[0]?.id, service_id: sv.data[0].id, data: { _e2e: "true" } }).select("id").single();
  ok("create case", !c.error, c.error?.message); caseId = c.data?.id;
  const u = await sb.from("cases").update({ data: { _e2e: "true", note: "verify" } }).eq("id", caseId).select("data").single();
  ok("save data", u.data?.data?.note === "verify", u.error?.message);
  path = `${caseId}/uploads/verify.pdf`;
  const pdf = new Blob(["%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"], { type: "application/pdf" });
  const up = await sb.storage.from("case-files").upload(path, pdf, { contentType: "application/pdf" });
  ok("upload pdf", !up.error, up.error?.message);
  const d = await sb.from("documents").insert({ case_id: caseId, kind: "other", storage_path: path, source: "upload" });
  ok("documents row", !d.error, d.error?.message);
  const su = await sb.storage.from("case-files").createSignedUrl(path, 60);
  const r = su.data ? await fetch(su.data.signedUrl) : null;
  ok("read via signed url", r?.ok && (await r.text()).startsWith("%PDF"), su.error?.message);
  const bad = await sb.storage.from("case-files").upload(`${caseId}/other/x.pdf`, pdf);
  ok("upload outside uploads/ denied", !!bad.error);
  const k = await sb.from("consents").insert({ case_id: caseId, kind: "digilocker", text: "verify", channel: "crm" });
  ok("insert consent", !k.error, k.error?.message);
  const j = await sb.from("automation_jobs").insert({ case_id: caseId, kind: "digilocker_fetch", mode: "mock", status: "queued" });
  ok("insert digilocker_fetch job", !j.error, j.error?.message);
  const ev = await sb.from("case_events").select("id").eq("case_id", caseId);
  ok("read case_events", !ev.error, ev.error?.message);
  await sb.auth.signOut();
  const a = await sb.from("cases").select("id").limit(5);
  const an = await sb.from("services").select("id").limit(5);
  const st = await sb.storage.from("case-files").createSignedUrl(path, 60);
  ok("anon sees nothing", !a.data?.length && !an.data?.length && !st.data, "cases/services/storage leaked");
} catch (e) { ok("script error", false, e.message); }
finally {
  if (path) await admin.storage.from("case-files").remove([path]);
  if (caseId) await admin.from("cases").delete().eq("id", caseId);
  console.log("cleaned up");
}
process.exit(fails ? 1 : 0);
