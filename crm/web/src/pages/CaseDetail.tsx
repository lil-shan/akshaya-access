import { useCallback, useEffect, useState } from "react";
import { supabase } from "../supabase";
import { validate, type Field } from "../form";
import DynamicForm from "../DynamicForm";

type Case = { id: string; case_number: string; status: string; service_id: string; data: Record<string, string>; citizens: { full_name: string } | null;
  services: { name: string; name_ml: string; submission: string; fields: Field[]; documents: { kind: string; label: string; required: boolean }[] } };
type Ev = { id: number; at: string; actor: string; type: string; message: string | null };
type Doc = { id: string; kind: string; storage_path: string; source: string; url?: string };
type Job = { id: string; kind: string; mode: string; status: string; error: string | null; created_at: string };
const isImg = (p: string) => /\.(png|jpe?g)$/i.test(p);
const MAX = 10 * 1024 * 1024; const EXT: Record<string, string> = { "application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png" };
type Prompt = { id: string; job_id: string; kind: string; prompt_text: string | null; prompt_text_ml: string | null; media_path: string | null; expires_at: string | null; url?: string };

const DL_CONSENT = "The citizen consents to fetching their documents from DigiLocker (API Setu sandbox, canned dummy data only).";
const CONSENT_TEXT = "The citizen has consented to Akshaya-Access filling this form on their behalf using the details above, and to relaying OTP/captcha. Dummy data only; nothing is submitted to a real portal.";

async function signed(path: string | null) {
  if (!path) return undefined;
  const { data } = await supabase.storage.from("case-files").createSignedUrl(path, 600);
  return data?.signedUrl;
}

function PromptPanel({ p, onDone }: { p: Prompt; onDone: () => void }) {
  const [answer, setAnswer] = useState(""); const [err, setErr] = useState("");
  async function submit() {
    // The answer is only written to job_prompts.answer; never to case_events.
    const { error } = await supabase.from("job_prompts").update({ answer, status: "answered", answered_at: new Date().toISOString() }).eq("id", p.id).eq("status", "open");
    if (error) setErr(error.message); else { setAnswer(""); onDone(); }
  }
  return (
    <div className="card" style={{ borderColor: "#e6a700", borderWidth: 3 }}>
      <h2>Citizen prompt: {p.kind}</h2>
      <p>{p.prompt_text}</p>{p.prompt_text_ml && <p className="ml">{p.prompt_text_ml}</p>}
      {p.expires_at && <p><small>Expires {new Date(p.expires_at).toLocaleTimeString()}</small></p>}
      {p.kind === "captcha_audio" && (p.url ? <audio controls src={p.url} /> : <p className="err">Audio not available</p>)}
      {p.kind === "captcha_image" && (p.url ? <img src={p.url} alt="captcha" style={{ maxWidth: "100%" }} /> : <p className="err">Image not available</p>)}
      <input autoComplete="off" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder={p.kind === "confirm" ? "yes / no" : "Answer"} />
      <button onClick={submit} disabled={!answer.trim()}>Submit answer</button>{err && <span className="err">{err}</span>}
    </div>
  );
}

export default function CaseDetail({ id }: { id: string }) {
  const [c, setC] = useState<Case | null>(null); const [events, setEvents] = useState<Ev[]>([]); const [docs, setDocs] = useState<Doc[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]); const [prompts, setPrompts] = useState<Prompt[]>([]); const [consents, setConsents] = useState<{ id: string; given_at: string; kind: string }[]>([]);
  const [values, setValues] = useState<Record<string, string>>({}); const [errors, setErrors] = useState<Record<string, string>>({});
  const [upKind, setUpKind] = useState(""); const [agree, setAgree] = useState(false); const [msg, setMsg] = useState("");

  const loadCase = useCallback(async () => {
    const { data } = await supabase.from("cases").select("*,citizens(full_name),services(name,name_ml,submission,fields,documents)").eq("id", id).single();
    setC(data as unknown as Case | null);
  }, [id]);
  const loadRest = useCallback(async () => {
    const [e, d, j, k] = await Promise.all([
      supabase.from("case_events").select("id,at,actor,type,message").eq("case_id", id).order("at", { ascending: false }),
      supabase.from("documents").select("*").eq("case_id", id).order("created_at"),
      supabase.from("automation_jobs").select("id,kind,mode,status,error,created_at").eq("case_id", id).order("created_at", { ascending: false }),
      supabase.from("consents").select("id,given_at,kind").eq("case_id", id).order("given_at", { ascending: false }),
    ]);
    setEvents((e.data as Ev[]) ?? []); setJobs((j.data as Job[]) ?? []); setConsents(k.data ?? []);
    setDocs(await Promise.all(((d.data as Doc[]) ?? []).map(async (x) => ({ ...x, url: await signed(x.storage_path) }))));
    const jobIds = ((j.data as Job[]) ?? []).map((x) => x.id);
    if (jobIds.length) {
      const { data: pr } = await supabase.from("job_prompts").select("id,job_id,kind,prompt_text,prompt_text_ml,media_path,expires_at").in("job_id", jobIds).eq("status", "open");
      setPrompts(await Promise.all(((pr as Prompt[]) ?? []).map(async (x) => ({ ...x, url: await signed(x.media_path) }))));
    } else setPrompts([]);
  }, [id]);
  const reload = useCallback(() => { loadCase(); loadRest(); }, [loadCase, loadRest]);

  useEffect(() => {
    reload();
    const ch = supabase.channel(`case-${id}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "cases", filter: `id=eq.${id}` }, loadCase)
      .on("postgres_changes", { event: "*", schema: "public", table: "case_events", filter: `case_id=eq.${id}` }, loadRest)
      .on("postgres_changes", { event: "*", schema: "public", table: "automation_jobs", filter: `case_id=eq.${id}` }, loadRest)
      .on("postgres_changes", { event: "*", schema: "public", table: "job_prompts" }, loadRest)
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, [id, reload, loadCase, loadRest]);
  useEffect(() => { if (c) setValues(c.data ?? {}); }, [c?.id, c?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!c) return <div className="card">Loading…</div>;
  const failedMissing = jobs.find((j) => j.status === "failed" && j.error?.startsWith("missing_fields:"));
  const missing = failedMissing ? failedMissing.error!.slice(15).split(",").map((k) => k.trim()).filter(Boolean) : [];
  const shownErrors = { ...Object.fromEntries(missing.map((k) => [k, "Missing or invalid (reported by automation)"])), ...errors };
  const editable = c.status === "draft" || c.status === "ready";
  const fields = c.services.fields;

  async function save(): Promise<boolean> {
    const e = validate(fields, values); setErrors(e);
    const status = Object.keys(e).length === 0 ? "ready" : "draft";
    const { error } = await supabase.from("cases").update({ data: values, status }).eq("id", id);
    if (error) { setMsg(error.message); return false; }
    await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "data_saved", message: `Details saved (${status})` });
    setMsg(status === "ready" ? "Saved. Case is ready." : "Saved as draft: fix the highlighted fields."); return status === "ready";
  }
  async function run() {
    if (!agree) return;
    if (!(await save())) return;
    const sub = c!.services.submission;
    const { error: ce } = await supabase.from("consents").insert({ case_id: id, kind: "automation_run", text: CONSENT_TEXT, channel: "crm" });
    if (ce) return setMsg(ce.message);
    const { error } = await supabase.from("automation_jobs").insert({ case_id: id, kind: sub === "pdf" ? "fill_pdf" : "portal_fill", mode: sub === "portal_dry_run" ? "dry_run" : "mock", status: "queued" });
    if (error) return setMsg(error.message);
    await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "automation_queued", message: "Consent recorded; automation job queued" });
    setMsg("Automation queued."); setAgree(false);
  }
  async function upload(file: File | undefined) {
    if (!file) return;
    const ext = EXT[file.type];
    if (!ext) return setMsg("Only PDF, JPG or PNG files are allowed.");
    if (file.size > MAX) return setMsg("File is larger than 10 MB.");
    const kind = upKind || "other";
    const path = `${id}/uploads/${crypto.randomUUID()}.${ext}`;
    const { error } = await supabase.storage.from("case-files").upload(path, file, { contentType: file.type });
    if (error) return setMsg(error.message);
    const { error: de } = await supabase.from("documents").insert({ case_id: id, kind, storage_path: path, source: "upload" });
    if (de) return setMsg(de.message);
    await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "document_uploaded", message: `Uploaded ${kind}` });
    setMsg("Saved. Document uploaded."); loadRest();
  }
  async function digilocker() {
    const { error: ce } = await supabase.from("consents").insert({ case_id: id, kind: "digilocker", text: DL_CONSENT, channel: "crm" });
    if (ce) return setMsg(ce.message);
    const { error } = await supabase.from("automation_jobs").insert({ case_id: id, kind: "digilocker_fetch", mode: "mock", status: "queued" });
    if (error) return setMsg(error.message);
    await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "digilocker_queued", message: "DigiLocker (sandbox) consent recorded; fetch queued" });
    setMsg("Saved. DigiLocker fetch queued.");
  }
  async function cancel() {
    await supabase.from("cases").update({ status: "cancelled" }).eq("id", id);
    await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "cancelled", message: "Case cancelled" });
  }

  return (
    <>
      <div className="card"><h1>Case {c.case_number} <span className={`badge ${c.status}`}>{c.status}</span></h1>
        <p>{c.citizens?.full_name} · {c.services.name} <span className="ml">{c.services.name_ml}</span></p></div>
      {prompts.map((p) => <PromptPanel key={p.id} p={p} onDone={loadRest} />)}
      <div className="card"><h2>Details</h2>
        <DynamicForm fields={fields} values={values} errors={shownErrors} disabled={!editable} onChange={(k, v) => setValues({ ...values, [k]: v })} />
        {editable && <button onClick={save}>Save details</button>}{msg && <span className={msg.startsWith("Saved") || msg === "Automation queued." ? "ok" : "err"}> {msg}</span>}
      </div>
      <div className="card"><h2>Documents</h2>
        <ul>{c.services.documents.map((d) => { const have = docs.filter((x) => x.kind === d.kind);
          return <li key={d.kind}>{have.length ? "✔" : "○"} {d.label} {d.required ? "" : "(optional)"}</li>; })}</ul>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>{docs.map((x) => <div key={x.id} style={{ maxWidth: 160 }}>
          {x.url && isImg(x.storage_path) && <a href={x.url} target="_blank" rel="noreferrer"><img src={x.url} alt={x.kind} style={{ width: 150, border: "1px solid #ccc" }} /></a>}
          <div>{x.url ? <a href={x.url} target="_blank" rel="noreferrer">{x.kind}</a> : x.kind} <small>[{x.source}]</small></div></div>)}</div>
        {!docs.length && <p>No documents yet.</p>}
        <h3>Upload (PDF/JPG/PNG, max 10 MB)</h3>
        <select value={upKind} onChange={(e) => setUpKind(e.target.value)}><option value="">other</option>{c.services.documents.map((d) => <option key={d.kind} value={d.kind}>{d.label}</option>)}</select>
        <input type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
      <div className="card"><h2>Automation</h2>
        {consents.length > 0 && <p className="ok">Consent recorded {new Date(consents[0].given_at).toLocaleString()}</p>}
        {editable && <><label><input type="checkbox" style={{ width: "auto" }} checked={agree} onChange={(e) => setAgree(e.target.checked)} /> {CONSENT_TEXT}</label>
          <button onClick={run} disabled={!agree}>Run automation</button><button className="sec" onClick={cancel}>Cancel case</button></>}
        <button className="sec" onClick={digilocker}>Fetch from DigiLocker (sandbox)</button>
        {jobs.map((j) => <div key={j.id}>{j.kind} ({j.mode}) · <b>{j.status}</b> {j.error && <span className="err">{j.error.startsWith("missing_fields:") ? `Missing or invalid fields: ${j.error.slice(15)}` : j.error}</span>}</div>)}
      </div>
      <div className="card"><h2>Timeline</h2>
        {events.map((e) => <div className="ev" key={e.id}><small>{new Date(e.at).toLocaleString()} · {e.actor} · {e.type}</small><div>{e.message}</div></div>)}
        {!events.length && <p>No events yet.</p>}</div>
    </>
  );
}
