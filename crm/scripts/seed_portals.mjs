// Usage: set -a; . ../.cloud.env; set +a; node scripts/seed_portals.mjs
// Seeds voter_form6 and thuna_lost_property from automation/portals/<service>/fields.json (array of fields, or {fields,documents,name,name_ml,notes}).
import { readFileSync, existsSync } from "node:fs";
import { createClient } from "../web/node_modules/@supabase/supabase-js/dist/index.mjs";
const admin = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
const META = {
  voter_form6: ["New voter registration (ECI Form 6) - real portal dry run", "പുതിയ വോട്ടർ രജിസ്ട്രേഷൻ (ഫോം 6)", [
    { kind: "photo", label: "Passport-size photo", label_ml: "ഫോട്ടോ", required: true }, { kind: "age_proof", label: "Age proof (birth certificate / SSLC)", label_ml: "പ്രായം തെളിയിക്കുന്ന രേഖ", required: true },
    { kind: "address_proof", label: "Address proof (Aadhaar / ration card)", label_ml: "വിലാസ രേഖ", required: true }]],
  thuna_lost_property: ["Lost property / document report (Kerala Police Thuna) - real portal dry run", "നഷ്ടപ്പെട്ട വസ്തു / രേഖ റിപ്പോർട്ട് (തുണ)", [
    { kind: "id_proof", label: "ID proof of the reporter", label_ml: "തിരിച്ചറിയൽ രേഖ", required: true }]],
};
for (const [id, [name, name_ml, docs]] of Object.entries(META)) {
  const f = new URL(`../../automation/portals/${id}/fields.json`, import.meta.url);
  if (!existsSync(f)) { console.log(`MISSING ${id}`); process.exitCode = 2; continue; }
  const j = JSON.parse(readFileSync(f, "utf8")); const fields = Array.isArray(j) ? j : j.fields;
  const row = { id, name: j.name ?? name, name_ml: j.name_ml ?? name_ml, tier: 2, submission: "portal_dry_run", fields, documents: j.documents ?? docs, fee: { amount_inr: 0 }, active: true,
    notes: j.notes ?? "REAL portal dry run: stops before submit. Login mobile is requested at run time and never stored." };
  const { error } = await admin.from("services").upsert(row);
  console.log(error ? `FAIL ${id}: ${error.message}` : `SEEDED ${id} (${fields.length} fields)`);
}
