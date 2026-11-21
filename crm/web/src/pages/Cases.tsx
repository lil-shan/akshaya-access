import { useEffect, useState } from "react";
import { supabase } from "../supabase";
import { STATUSES, STATUS_LABEL, Status } from "../ui";
export { STATUSES };

type Row = { id: string; case_number: string; status: string; service_id: string; channel: string; created_at: string; citizens: { full_name: string } | null };

export default function Cases() {
  const [rows, setRows] = useState<Row[]>([]); const [status, setStatus] = useState(() => new URLSearchParams(location.hash.split("?")[1] ?? "").get("status") ?? ""); const [service, setService] = useState("");
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
  const name = (id: string) => services.find((s) => s.id === id)?.name ?? id;
  return (
    <>
      <div className="page-head"><div><h1>All cases</h1><p>എല്ലാ കേസുകളും</p></div><a href="#/new"><button>New case</button></a></div>
      <div className="card">
        <div className="filters">
          <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</select>
          <select aria-label="Service" value={service} onChange={(e) => setService(e.target.value)}><option value="">All services</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        </div>
        <div className="tbl-wrap"><table><thead><tr><th>Case</th><th>Citizen</th><th>Service</th><th>Status</th><th>Channel</th></tr></thead><tbody>
          {shown.map((r) => <tr key={r.id} className="row" tabIndex={0} onClick={() => (location.hash = `#/case/${r.id}`)} onKeyDown={(e) => e.key === "Enter" && (location.hash = `#/case/${r.id}`)}>
            <td><b>{r.case_number}</b></td><td>{r.citizens?.full_name}</td><td>{name(r.service_id)}</td><td><Status s={r.status} /></td><td>{r.channel}</td></tr>)}
          {!shown.length && <tr><td colSpan={5}>No cases match. Clear a filter or create a new case.</td></tr>}
        </tbody></table></div></div>
    </>
  );
}
