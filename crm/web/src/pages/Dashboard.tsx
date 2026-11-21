import { useEffect, useState } from "react";
import { supabase } from "../supabase";
import { STATUSES, STATUS_LABEL, Status, when } from "../ui";

type Row = { id: string; case_number: string; status: string; service_id: string; created_at: string; updated_at?: string; citizens: { full_name: string } | null; services: { name: string; name_ml: string } | null };
type Ev = { id: number; case_id: string; at: string; type: string; message: string | null; cases: { case_number: string } | null };
type Open = { id: string; kind: string; prompt_text: string | null; automation_jobs: { case_id: string } | null };

export default function Dashboard() {
  const [rows, setRows] = useState<Row[]>([]); const [events, setEvents] = useState<Ev[]>([]); const [open, setOpen] = useState<Open[]>([]);
  useEffect(() => {
    const load = () => {
      supabase.from("cases").select("id,case_number,status,service_id,created_at,citizens(full_name),services(name,name_ml)").order("created_at", { ascending: false }).limit(500).then(({ data }) => setRows((data as unknown as Row[]) ?? []));
      supabase.from("case_events").select("id,case_id,at,type,message,cases(case_number)").order("at", { ascending: false }).limit(8).then(({ data }) => setEvents((data as unknown as Ev[]) ?? []));
      supabase.from("job_prompts").select("id,kind,prompt_text,automation_jobs(case_id)").eq("status", "open").then(({ data }) => setOpen((data as unknown as Open[]) ?? []));
    };
    load();
    const ch = supabase.channel("dash").on("postgres_changes", { event: "*", schema: "public", table: "cases" }, load).on("postgres_changes", { event: "*", schema: "public", table: "job_prompts" }, load).subscribe();
    return () => { supabase.removeChannel(ch); };
  }, []);
  const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
  const needs = open.map((p) => ({ p, c: p.automation_jobs ? byId[p.automation_jobs.case_id] : undefined })).filter((x) => x.c);
  return (
    <>
      <div className="page-head"><div><h1>Today's work</h1><p>ഇന്നത്തെ അപേക്ഷകൾ</p></div><a href="#/new"><button>New case</button></a></div>
      <section className="attention" aria-label="Needs the citizen">
        <h2>{needs.length ? `${needs.length} waiting for the citizen` : "No citizen is being waited on"} <span className="ml">പൗരന്റെ മറുപടി കാത്തിരിക്കുന്നു</span></h2>
        {needs.map(({ p, c }) => <a key={p.id} className="attn-row" href={`#/case/${c!.id}`}>
          <b>{c!.case_number}</b><span>{c!.citizens?.full_name}</span><span>{c!.services?.name}</span><span className="badge waiting_citizen k">Needs {p.kind.replace("_", " ")}</span></a>)}
        {!needs.length && <p className="empty">When automation asks for an OTP, captcha or password, the case appears here first.</p>}
      </section>
      <div className="counts">{STATUSES.map((s) => <a key={s} className={`count ${s}`} href={`#/cases?status=${s}`}><b>{rows.filter((r) => r.status === s).length}</b><span>{STATUS_LABEL[s]}</span></a>)}</div>
      <div className="card"><h2>Recent activity</h2>
        <ul className="timeline">{events.map((e) => <li key={e.id}><small>{when(e.at)}</small><div><a href={`#/case/${e.case_id}`}>{e.cases?.case_number}</a> {e.message ?? e.type}</div></li>)}</ul>
        {!events.length && <p className="empty">Nothing yet.</p>}</div>
      <div className="card"><h2>Latest cases</h2><div className="tbl-wrap"><table><tbody>
        {rows.slice(0, 5).map((r) => <tr key={r.id} className="row" tabIndex={0} onClick={() => (location.hash = `#/case/${r.id}`)} onKeyDown={(e) => e.key === "Enter" && (location.hash = `#/case/${r.id}`)}>
          <td>{r.case_number}</td><td>{r.citizens?.full_name}</td><td>{r.services?.name}</td><td><Status s={r.status} /></td></tr>)}</tbody></table></div></div>
    </>
  );
}
