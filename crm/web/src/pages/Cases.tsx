import { useEffect, useState } from "react";
import { supabase } from "../supabase";

type Row = { id: string; case_number: string; status: string; service_id: string; channel: string; created_at: string; citizens: { full_name: string } | null };
export const STATUSES = ["draft", "ready", "running", "waiting_citizen", "done", "failed", "cancelled"];

export default function Cases() {
  const [rows, setRows] = useState<Row[]>([]); const [status, setStatus] = useState(""); const [service, setService] = useState("");
  const [services, setServices] = useState<{ id: string; name: string }[]>([]);
  useEffect(() => { supabase.from("services").select("id,name").then(({ data }) => setServices(data ?? [])); }, []);
  useEffect(() => {
    const load = () => supabase.from("cases").select("id,case_number,status,service_id,channel,created_at,citizens(full_name)")
      .order("created_at", { ascending: false }).limit(200).then(({ data }) => setRows((data as unknown as Row[]) ?? []));
    load();
    const ch = supabase.channel("cases-list").on("postgres_changes", { event: "*", schema: "public", table: "cases" }, load).subscribe();
    return () => { supabase.removeChannel(ch); };
  }, []);
  const shown = rows.filter((r) => (!status || r.status === status) && (!service || r.service_id === service));
  return (
    <div className="card"><h1>Cases</h1>
      <div className="filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select>
        <select value={service} onChange={(e) => setService(e.target.value)}><option value="">All services</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </div>
      <table><thead><tr><th>Case</th><th>Citizen</th><th>Service</th><th>Status</th><th>Channel</th></tr></thead><tbody>
        {shown.map((r) => <tr key={r.id} className="row" onClick={() => (location.hash = `#/case/${r.id}`)}>
          <td>{r.case_number}</td><td>{r.citizens?.full_name}</td><td>{r.service_id}</td><td><span className={`badge ${r.status}`}>{r.status}</span></td><td>{r.channel}</td></tr>)}
        {!shown.length && <tr><td colSpan={5}>No cases.</td></tr>}
      </tbody></table></div>
  );
}
