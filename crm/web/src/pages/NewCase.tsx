import { useEffect, useState } from "react";
import { supabase } from "../supabase";
import { prefill, validate, type Field } from "../form";
import DynamicForm from "../DynamicForm";
import { Tier } from "../ui";

type Svc = { id: string; name: string; name_ml?: string; submission?: string; category?: string | null; fields: Field[] };
type Cit = { id: string; full_name: string; [k: string]: unknown };

export default function NewCase() {
  const [citizens, setCitizens] = useState<Cit[]>([]); const [services, setServices] = useState<Svc[]>([]);
  const [cid, setCid] = useState(""); const [sid, setSid] = useState(""); const [q, setQ] = useState("");
  const [values, setValues] = useState<Record<string, string>>({}); const [errors, setErrors] = useState<Record<string, string>>({}); const [msg, setMsg] = useState("");
  useEffect(() => {
    supabase.from("citizens").select("*").order("full_name").then(({ data }) => setCitizens((data as Cit[]) ?? []));
    supabase.from("services").select("*").eq("active", true).then(({ data }) => setServices((data as Svc[]) ?? []));
  }, []);
  const svc = services.find((s) => s.id === sid);
  useEffect(() => { // prefill when citizen/service change
    if (svc) setValues(prefill(svc.fields, citizens.find((c) => c.id === cid) ?? null));
    setErrors({});
  }, [cid, sid, svc, citizens]);

  const ql = q.trim().toLowerCase();
  const match = services.filter((s) => !ql || `${s.name} ${s.name_ml ?? ""} ${s.category ?? ""}`.toLowerCase().includes(ql));
  const groups: Record<string, Svc[]> = {};
  for (const s of match) (groups[s.category?.trim() || "Other"] ??= []).push(s);
  const cats = Object.keys(groups).sort((a, b) => (a === "Other" ? 1 : b === "Other" ? -1 : a.localeCompare(b)));

  async function save() {
    if (!svc || !cid) return setMsg("Pick a citizen and a service.");
    const e = validate(svc.fields, values); setErrors(e);
    const complete = Object.keys(e).length === 0;
    // Incomplete cases may be saved as draft; "ready" only when valid.
    const { data, error } = await supabase.from("cases").insert({ citizen_id: cid, service_id: sid, channel: "crm", data: values, status: complete ? "ready" : "draft" }).select("id").single();
    if (error || !data) return setMsg(error?.message ?? "Failed");
    await supabase.from("case_events").insert({ case_id: data.id, actor: "crm_user", type: "case_created", message: complete ? "Case created (ready)" : "Case created as draft (incomplete)" });
    location.hash = `#/case/${data.id}`;
  }
  return (
    <>
      <div className="page-head"><div><h1>New case</h1><p>പുതിയ കേസ്</p></div></div>
      <div className="card"><h2>1. Citizen</h2>
        <select aria-label="Citizen" value={cid} onChange={(e) => setCid(e.target.value)}><option value="">Select…</option>{citizens.map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}</select></div>
      <div className="card"><h2>2. Service <span className="ml">സേവനം</span></h2>
        <input className="search" type="search" aria-label="Search services" placeholder="Search in English or മലയാളം" value={q} onChange={(e) => setQ(e.target.value)} />
        {svc && <p className="chosen"><b>Selected:</b> {svc.name} {svc.name_ml && <span className="ml">{svc.name_ml}</span>} {svc.submission && <Tier t={svc.submission} />}</p>}
        {cats.map((cat) => <section className="cat" key={cat}><h3>{cat} <small>{groups[cat].length}</small></h3>
          <div className="svc-grid">{groups[cat].sort((a, b) => a.name.localeCompare(b.name)).map((s) =>
            <button type="button" key={s.id} className="svc" aria-pressed={s.id === sid} onClick={() => setSid(s.id)}>
              <b>{s.name}</b>{s.name_ml && <span className="ml">{s.name_ml}</span>}{s.submission && <Tier t={s.submission} />}</button>)}</div></section>)}
        {!cats.length && <p className="empty">No service matches "{q}".</p>}</div>
      {svc && <div className="card"><h2>3. Details</h2><DynamicForm fields={svc.fields} values={values} errors={errors} onChange={(k, v) => setValues({ ...values, [k]: v })} /></div>}
      <button onClick={save} disabled={!svc || !cid}>Create case</button>{msg && <span className="err">{msg}</span>}
    </>
  );
}
