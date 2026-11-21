export type Field = {
  key: string; label: string; label_ml?: string; type: "text" | "date" | "number" | "phone" | "select" | "yesno" | "ifsc" | "account_number";
  required?: boolean; pattern?: string | null; ask_ml?: string; source?: string | null; options?: string[];
};
export type Citizen = Record<string, unknown>;

/** Resolve "citizen.address.line" style paths against the citizen record. */
export function prefill(fields: Field[], citizen: Citizen | null): Record<string, string> {
  const out: Record<string, string> = {};
  if (!citizen) return out;
  for (const f of fields) {
    if (!f.source?.startsWith("citizen.")) continue;
    let v: unknown = citizen;
    for (const p of f.source.slice(8).split(".")) v = (v as Record<string, unknown> | null)?.[p];
    if (v !== undefined && v !== null && v !== "") out[f.key] = String(v);
  }
  return out;
}

const BUILTIN: Partial<Record<Field["type"], RegExp>> = {
  phone: /^[0-9]{10}$/, ifsc: /^[A-Z]{4}0[A-Z0-9]{6}$/, account_number: /^[0-9]{9,18}$/, number: /^[0-9]+(\.[0-9]+)?$/,
};

/** Returns {fieldKey: message} for invalid fields; empty object means valid. */
export function validate(fields: Field[], data: Record<string, unknown>): Record<string, string> {
  const errs: Record<string, string> = {};
  for (const f of fields) {
    const v = String(data[f.key] ?? "").trim();
    if (!v) { if (f.required) errs[f.key] = "Required"; continue; }
    if (f.type === "date" && (!/^\d{4}-\d{2}-\d{2}$/.test(v) || isNaN(Date.parse(v)))) errs[f.key] = "Invalid date";
    else if (f.type === "select" && f.options && !f.options.includes(v)) errs[f.key] = "Pick an option";
    else if (f.type === "yesno" && v !== "yes" && v !== "no") errs[f.key] = "Yes or no";
    else if (BUILTIN[f.type] && !BUILTIN[f.type]!.test(v)) errs[f.key] = "Invalid " + f.type.replace("_", " ");
    else if (f.pattern && !new RegExp(f.pattern).test(v)) errs[f.key] = "Wrong format";
  }
  return errs;
}
