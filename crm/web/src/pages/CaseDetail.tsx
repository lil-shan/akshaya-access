import { useCallback, useEffect, useRef, useState } from "react";
import { supabase } from "../supabase";
import { validate, type Field } from "../form";
import DynamicForm from "../DynamicForm";
import QRCode from "qrcode";

function Qr({ text }: { text: string }) {
  const [src, setSrc] = useState("");
  useEffect(() => { QRCode.toDataURL(text, { width: 180, margin: 1 }).then(setSrc).catch(() => setSrc("")); }, [text]);
  return src ? <img src={src} alt="QR code" width={180} height={180} /> : null;
}
const URL_RE = /https?:\/\/[^\s)]+/;
type Bill = { customer_name?: string; amount_inr?: number; due_date?: string; sandbox?: boolean };
type Pay = { id: string; provider: string; amount_inr: number; status: string; reference: string | null; created_at: string };

type Case = { id: string; case_number: string; status: string; service_id: string; data: Record<string, string>; citizens: { full_name: string } | null;
  services: { name: string; name_ml: string; submission: string; fields: Field[]; documents: { kind: string; label: string; required: boolean }[] } };
type Ev = { id: number; at: string; actor: string; type: string; message: string | null };
type Doc = { id: string; kind: string; storage_path: string; source: string; url?: string };
type Job = { id: string; kind: string; mode: string; status: string; error: string | null; created_at: string; result: Result | null };
type Result = { screenshots?: (string | { path?: string })[]; output_pdf?: string | null; stopped_before_submit?: boolean; summary?: string; digilocker_docs?: (string | { path?: string; kind?: string })[] };
type Link = { path: string; url?: string };
const isImg = (p: string) => /\.(png|jpe?g)$/i.test(p);
const MAX = 10 * 1024 * 1024; const EXT: Record<string, string> = { "application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png" };
type Prompt = { id: string; job_id: string; kind: string; prompt_text: string | null; prompt_text_ml: string | null; media_path: string | null; expires_at: string | null; url?: string };

const DRY_WARNING = "This opens the REAL portal and sends a REAL OTP to your phone. Nothing will be submitted.";
const DRY_CONSENT = "I am this citizen and this is my own phone number. " + DRY_WARNING;
const pathOf = (x: string | { path?: string }) => (typeof x === "string" ? x : x?.path ?? "");

function Countdown({ to }: { to: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const s = Math.max(0, Math.floor((new Date(to).getTime() - now) / 1000));
  return <small className={s < 15 ? "err" : ""}>{s ? `Expires in ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : "Expired"}</small>;
}

const DL_CONSENT = "The citizen consents to fetching their documents from DigiLocker (API Setu sandbox, canned dummy data only).";
const CONSENT_TEXT = "The citizen has consented to Akshaya-Access filling this form on their behalf using the details above, and to relaying OTP/captcha. Dummy data only; nothing is submitted to a real portal.";

async function signed(path: string | null) {
  if (!path) return undefined;
  const { data } = await supabase.storage.from("case-files").createSignedUrl(path, 600);
  return data?.signedUrl;
}

function PromptPanel({ p, onDone }: { p: Prompt; onDone: () => void }) {
  const [answer, setAnswer] = useState(""); const [err, setErr] = useState("");
  const pw = useRef<HTMLInputElement>(null);
  async function submitPw() {
    const v = pw.current?.value ?? ""; if (!v) return;
    const { error } = await supabase.from("job_prompts").update({ answer: v, status: "answered", answered_at: new Date().toISOString() }).eq("id", p.id).eq("status", "open");
    if (pw.current) pw.current.value = "";
    if (error) setErr(error.message); else onDone();
  }
  const link = p.kind === "confirm" ? p.prompt_text?.match(URL_RE)?.[0] : undefined;
  async function approve() {
    const { error } = await supabase.from("job_prompts").update({ answer: "yes", status: "answered", answered_at: new Date().toISOString() }).eq("id", p.id).eq("status", "open");
    if (error) setErr(error.message); else onDone();
  }
  async function submit() {
    // The answer is only written to job_prompts.answer; never to case_events.
    const { error } = await supabase.from("job_prompts").update({ answer, status: "answered", answered_at: new Date().toISOString() }).eq("id", p.id).eq("status", "open");
    if (error) setErr(error.message); else { setAnswer(""); onDone(); }
  }
  return (
    <div className="card" style={{ borderColor: "#e6a700", borderWidth: 3 }}>
      <h2>Citizen prompt: {p.kind}</h2>
      <p>{p.prompt_text}</p>{p.prompt_text_ml && <p className="ml">{p.prompt_text_ml}</p>}
      {p.expires_at && <p><Countdown to={p.expires_at} /></p>}
      {p.kind === "captcha_audio" && (p.url ? <audio controls src={p.url} /> : <p className="err">Audio not available</p>)}
      {p.kind === "captcha_image" && (p.url ? <img src={p.url} alt="captcha" style={{ maxWidth: "100%" }} /> : <p className="err">Image not available</p>)}
      {link && <div><p><a href={link} target="_blank" rel="noreferrer">Open consent link</a></p><Qr text={link} /><p><button onClick={approve}>I have approved it</button>{err && <span className="err"> {err}</span>}</p></div>}
      {p.kind === "password" && <div><input ref={pw} type="password" autoComplete="off" name={`pw-${p.id}`} placeholder="Thuna password" /><button onClick={submitPw}>Submit password</button>{err && <span className="err"> {err}</span>}<p><small>Used once and erased.</small></p></div>}
      {!link && p.kind !== "password" && <><input autoComplete="off" type={p.kind === "field" ? "tel" : "text"} inputMode={p.kind === "field" || p.kind === "otp" ? "numeric" : undefined} name={`prompt-${p.id}`} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder={p.kind === "confirm" ? "yes / no" : "Answer"} />
      <button onClick={submit} disabled={!answer.trim()}>Submit answer</button>{err && <span className="err">{err}</span>}</>}
    </div>
  );
}

export default function CaseDetail({ id }: { id: string }) {
  const [c, setC] = useState<Case | null>(null); const [events, setEvents] = useState<Ev[]>([]); const [docs, setDocs] = useState<Doc[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]); const [prompts, setPrompts] = useState<Prompt[]>([]); const [consents, setConsents] = useState<{ id: string; given_at: string; kind: string }[]>([]);
  const [values, setValues] = useState<Record<string, string>>({}); const [errors, setErrors] = useState<Record<string, string>>({});
  const [links, setLinks] = useState<Record<string, Link[]>>({}); const [dryOpen, setDryOpen] = useState(false); const [dryOk, setDryOk] = useState(false);
  const [pays, setPays] = useState<Pay[]>([]); const [payOpen, setPayOpen] = useState(false); const [payOk, setPayOk] = useState(false);
  const [upKind, setUpKind] = useState(""); const [agree, setAgree] = useState(false); const [msg, setMsg] = useState("");

  const loadCase = useCallback(async () => {
    const { data } = await supabase.from("cases").select("*,citizens(full_name),services(name,name_ml,submission,fields,documents)").eq("id", id).single();
    setC(data as unknown as Case | null);
  }, [id]);
  const loadRest = useCallback(async () => {
    supabase.from("payments").select("id,provider,amount_inr,status,reference,created_at").eq("case_id", id).order("created_at", { ascending: false }).then(({ data }) => setPays((data as Pay[]) ?? []));
    const [e, d, j, k] = await Promise.all([
      supabase.from("case_events").select("id,at,actor,type,message").eq("case_id", id).order("at", { ascending: false }),
      supabase.from("documents").select("*").eq("case_id", id).order("created_at"),
      supabase.from("automation_jobs").select("id,kind,mode,status,error,created_at,result").eq("case_id", id).order("created_at", { ascending: false }),
      supabase.from("consents").select("id,given_at,kind").eq("case_id", id).order("given_at", { ascending: false }),
    ]);
    setEvents((e.data as Ev[]) ?? []); setJobs((j.data as Job[]) ?? []); setConsents(k.data ?? []);
    setDocs(await Promise.all(((d.data as Doc[]) ?? []).map(async (x) => ({ ...x, url: await signed(x.storage_path) }))));
    const lk: Record<string, Link[]> = {};
    await Promise.all(((j.data as Job[]) ?? []).map(async (jb) => {
      const r = jb.result; if (!r) return;
      const ps = [...(r.screenshots ?? []).map(pathOf), pathOf(r.output_pdf ?? ""), ...(r.digilocker_docs ?? []).map(pathOf)].filter(Boolean);
      lk[jb.id] = await Promise.all(ps.map(async (path) => ({ path, url: await signed(path) })));
    }));
    setLinks(lk);
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
      .on("postgres_changes", { event: "*", schema: "public", table: "payments", filter: `case_id=eq.${id}` }, loadRest)
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, [id, reload, loadCase, loadRest]);
  const anyPending = pays.some((x) => x.status === "pending") || jobs.some((x) => x.status === "queued" || x.status === "running");
  useEffect(() => { if (!anyPending) return; const t = setInterval(() => { loadCase(); loadRest(); }, 4000); return () => clearInterval(t); }, [anyPending, loadCase, loadRest]);
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
  async function dryRun() {
    if (!dryOk) return;
    if (!(await save())) { setDryOpen(false); return; }
    const { error: ce } = await supabase.from("consents").insert({ case_id: id, kind: "portal_dry_run", text: DRY_CONSENT, channel: "crm" });
    if (ce) return setMsg(ce.message);
    const { error } = await supabase.from("automation_jobs").insert({ case_id: id, kind: "portal_fill", mode: "dry_run", status: "queued" });
    if (error) return setMsg(error.message);
    await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "automation_queued", message: "Dry-run consent recorded; REAL-portal dry run queued (stops before submit)" });
    setMsg("Automation queued."); setDryOk(false); setDryOpen(false);
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
  async function fetchBill() {
    const { error } = await supabase.from("automation_jobs").insert({ case_id: id, kind: "bbps_fetch", mode: "mock", status: "queued" });
    if (error) return setMsg(error.message);
    await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "bbps_fetch_queued", message: "Bill fetch (sandbox) queued" });
    setMsg("Saved. Bill fetch queued.");
  }
  async function setPay(pid: string, status: "confirmed" | "failed") {
    const { error } = await supabase.from("payments").update({ status }).eq("id", pid).eq("status", "pending");
    if (error) setMsg(error.message); else { await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "payment_marked", message: `Demo payment marked ${status}` }); loadRest(); }
  }
  async function collectPayment() {
    const amt = (c!.data as unknown as { _bill?: Bill })._bill?.amount_inr;
    if (!payOk || amt == null) return;
    const { error: ce } = await supabase.from("consents").insert({ case_id: id, kind: "payment", text: `Citizen confirmed payment of ₹${amt} for this KSEB bill (Razorpay test mode, paid by the citizen in their own UPI app).`, channel: "crm" });
    if (ce) return setMsg(ce.message);
    const { error } = await supabase.from("automation_jobs").insert({ case_id: id, kind: "payment_collect", mode: "mock", status: "queued" });
    if (error) return setMsg(error.message);
    await supabase.from("case_events").insert({ case_id: id, actor: "crm_user", type: "payment_queued", message: `Payment consent recorded for ₹${amt}; payment link queued` });
    setMsg("Saved. Payment link queued."); setPayOk(false); setPayOpen(false);
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
      {c.service_id === "kseb_bill_payment" && (() => { const bill = (c.data as unknown as { _bill?: Bill })._bill;
        const pj = jobs.find((j) => j.kind === "payment_collect"); const upi = (pj?.result as unknown as { upi_uri?: string } | null)?.upi_uri; const short = (pj?.result as unknown as { short_url?: string; upi_uri?: string; eko_reference?: string; bill_pay_reference?: string } | null)?.short_url;
        const ref = (pj?.result as unknown as Record<string, unknown> | null) ?? {}; const eko = (ref.eko_reference ?? ref.bill_pay_reference ?? ref.eko_ref) as string | undefined;
        return <div className="card"><h2>KSEB bill payment</h2>
          <button onClick={fetchBill}>Fetch bill</button>
          {bill && <div className="card" style={{ marginTop: 8 }}><b>{bill.customer_name}</b> · ₹{bill.amount_inr} · due {bill.due_date} {bill.sandbox !== false && <span className="badge failed">SANDBOX</span>}
            <div><button onClick={() => setPayOpen(true)}>Collect payment</button></div></div>}
          {pays.map((p) => <div key={p.id} style={{ marginTop: 8 }}>Payment ₹{p.amount_inr} ({p.provider}) · <b className={p.status === "failed" ? "err" : p.status === "confirmed" ? "ok" : ""}>{p.status}</b>
            {p.status === "pending" && short && p === pays[0] && <div><a href={short} target="_blank" rel="noreferrer">{short}</a><div><Qr text={short} /></div><small>The citizen pays in their own UPI app. We never ask for a UPI PIN.</small></div>}
            {p.provider === "upi_qr_demo" && upi && p.status === "pending" && p === pays[0] && <div><p className="err"><b>DEMO ONLY — pays the team's own UPI ID. Never use with real citizens.</b></p><Qr text={upi} /><div><a href={upi}>Open in UPI app</a></div></div>}
            {p.provider === "upi_qr_demo" && p.status === "pending" && <div><button onClick={() => setPay(p.id, "confirmed")}>Mark received (demo)</button><button className="sec" onClick={() => setPay(p.id, "failed")}>Mark failed</button></div>}
            {p.status === "confirmed" && eko && <div><small>Eko bill-pay reference: {eko}</small></div>}</div>)}
        </div>; })()}
      {payOpen && (() => { const amt = (c.data as unknown as { _bill?: Bill })._bill?.amount_inr;
        return <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
        <div className="card" style={{ maxWidth: 480 }} role="dialog" aria-modal="true"><h2>Collect payment</h2>
          <p>Read back to the citizen: the bill amount is <b>₹{amt}</b>. They pay in their own UPI app; never ask for their UPI PIN.</p>
          <label><input type="checkbox" style={{ width: "auto" }} checked={payOk} onChange={(e) => setPayOk(e.target.checked)} /> Citizen confirmed ₹{amt}</label>
          <div><button onClick={collectPayment} disabled={!payOk}>Create payment link</button><button className="sec" onClick={() => { setPayOpen(false); setPayOk(false); }}>Close</button></div></div></div>; })()}
      <div className="card"><h2>Automation</h2>
        {consents.length > 0 && <p className="ok">Consent recorded {new Date(consents[0].given_at).toLocaleString()}</p>}
        {editable && <><label><input type="checkbox" style={{ width: "auto" }} checked={agree} onChange={(e) => setAgree(e.target.checked)} /> {CONSENT_TEXT}</label>
          <button onClick={run} disabled={!agree}>Run automation</button><button className="sec" onClick={cancel}>Cancel case</button></>}
        {editable && c.services.submission === "portal_dry_run" && <button style={{ background: "#b00020" }} onClick={() => setDryOpen(true)}>Dry run on REAL portal</button>}
        <button className="sec" onClick={digilocker}>Fetch from DigiLocker (sandbox)</button>
        {jobs.map((j) => { const ls = links[j.id] ?? []; const shots = (j.result?.screenshots ?? []).map(pathOf); const last = shots[shots.length - 1];
          const lnk = (path: string) => ls.find((l) => l.path === path);
          const extra = ls.filter((l) => !shots.includes(l.path));
          return <div key={j.id} style={{ marginTop: 10 }}>{j.kind} ({j.mode}) · <b>{j.status}</b>{" "}
            {j.mode === "dry_run" && <span className="badge failed" style={{ background: "#b00020", color: "#fff" }}>DRY RUN · will stop before submit</span>}{" "}
            {j.error && <span className="err">{j.error.startsWith("missing_fields:") ? `Missing or invalid fields: ${j.error.slice(15)}` : j.error}</span>}
            {j.result?.summary && <div><small>{j.result.summary}</small></div>}
            {shots.length > 0 && <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 6 }}>{shots.map((sp, i) => { const u = lnk(sp)?.url; const isLast = sp === last && j.result?.stopped_before_submit !== false;
              return <div key={sp + i} style={{ width: isLast ? 320 : 150, border: isLast ? "3px solid #e6a700" : "1px solid #ccc", padding: 2 }}>
                {u ? <a href={u} target="_blank" rel="noreferrer"><img src={u} alt={`step ${i + 1}`} style={{ width: "100%" }} /></a> : <small className="err">not available</small>}
                <small>{isLast ? "Stopped before submit" : `Step ${i + 1}`}</small></div>; })}</div>}
            {extra.map((l) => <div key={l.path}>{l.url ? <a href={l.url} target="_blank" rel="noreferrer">{l.path.split("/").pop()}</a> : <span className="err">{l.path} (unavailable)</span>}</div>)}
          </div>; })}
      </div>
      {dryOpen && <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
        <div className="card" style={{ maxWidth: 480 }} role="dialog" aria-modal="true"><h2>Dry run on REAL portal</h2>
          <p><b>{DRY_WARNING}</b></p>
          {c.service_id === "thuna_lost_property" && <p><b>Your Thuna password will be used once and erased</b></p>}
          <label><input type="checkbox" style={{ width: "auto" }} checked={dryOk} onChange={(e) => setDryOk(e.target.checked)} /> I am this citizen and this is my own phone number</label>
          <div><button onClick={dryRun} disabled={!dryOk}>Start dry run</button><button className="sec" onClick={() => { setDryOpen(false); setDryOk(false); }}>Close</button></div></div></div>}
      <div className="card"><h2>Timeline</h2>
        {events.map((e) => <div className="ev" key={e.id}><small>{new Date(e.at).toLocaleString()} · {e.actor} · {e.type}</small><div>{e.message}</div></div>)}
        {!events.length && <p>No events yet.</p>}</div>
    </>
  );
}
