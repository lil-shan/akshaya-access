import { useEffect, useState } from "react";
import { supabase } from "../supabase";
import { prefill, validate, type Field } from "../form";
import DynamicForm from "../DynamicForm";

type Svc = { id: string; name: string; fields: Field[] };
type Cit = { id: string; full_name: string; [k: string]: unknown };

export default function NewCase() {
  const [citizens, setCitizens] = useState<Cit[]>([]); const [services, setServices] = useState<Svc[]>([]);
  const [cid, setCid] = useState(""); const [sid, setSid] = useState("");
  const [values, setValues] = useState<Record<string, string>>({}); const [errors, setErrors] = useState<Record<string, string>>({}); const [msg, setMsg] = useState("");
  useEffect(() => {
    supabase.from("citizens").select("*").order("full_name").then(({ data }) => setCitizens((data as Cit[]) ?? []));
    supabase.from("services").select("id,name,fields").eq("active", true).then(({ data }) => setServices((data as Svc[]) ?? []));
  }, []);
  const svc = services.find((s) => s.id === sid);
  useEffect(() => { // prefill when citizen/service change
    if (svc) setValues(prefill(svc.fields, citizens.find((c) => c.id === cid) ?? null));
    setErrors({});
  }, [cid, sid, svc, citizens]);

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
    <div className="card"><h1>New case</h1>
      <label>Citizen<select value={cid} onChange={(e) => setCid(e.target.value)}><option value="">Select…</option>{citizens.map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}</select></label>
      <label>Service<select value={sid} onChange={(e) => setSid(e.target.value)}><option value="">Select…</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      {svc && <DynamicForm fields={svc.fields} values={values} errors={errors} onChange={(k, v) => setValues({ ...values, [k]: v })} />}
      <button onClick={save} disabled={!svc || !cid}>Create case</button>{msg && <span className="err">{msg}</span>}
    </div>
  );
}
