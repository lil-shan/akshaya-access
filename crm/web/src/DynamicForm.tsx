import type { Field } from "./form";

export default function DynamicForm({ fields, values, errors, disabled, onChange }: {
  fields: Field[]; values: Record<string, string>; errors: Record<string, string>; disabled?: boolean; onChange: (k: string, v: string) => void;
}) {
  return <div className="two">{fields.map((f) => (
    <label key={f.key}>{f.label}{f.required && " *"} <span className="ml">{f.label_ml}</span>
      {f.type === "select" || f.type === "yesno" ? (
        <select disabled={disabled} value={values[f.key] ?? ""} onChange={(e) => onChange(f.key, e.target.value)}>
          <option value="">—</option>{(f.type === "yesno" ? ["yes", "no"] : f.options ?? []).map((o) => <option key={o}>{o}</option>)}
        </select>
      ) : (
        <input disabled={disabled} type={f.type === "date" ? "date" : "text"} inputMode={["number", "phone", "account_number"].includes(f.type) ? "numeric" : undefined}
          value={values[f.key] ?? ""} onChange={(e) => onChange(f.key, f.type === "ifsc" ? e.target.value.toUpperCase() : e.target.value)} />
      )}
      {errors[f.key] && <span className="err field-err">{errors[f.key]}</span>}
    </label>))}</div>;
}
