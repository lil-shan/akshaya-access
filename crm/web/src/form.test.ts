import { describe, expect, it } from "vitest";
import { prefill, validate, type Field } from "./form";

const fields: Field[] = [
  { key: "name", label: "Name", type: "text", required: true, source: "citizen.full_name" },
  { key: "addr", label: "Addr", type: "text", source: "citizen.address.line" },
  { key: "dob", label: "DOB", type: "date", required: true, source: "citizen.dob" },
  { key: "ifsc", label: "IFSC", type: "ifsc", required: true },
  { key: "acct", label: "Acct", type: "account_number", pattern: "^[0-9]{9,18}$" },
  { key: "rel", label: "Rel", type: "select", options: ["Spouse", "Son"] },
  { key: "mobile", label: "Mobile", type: "phone", required: true },
];

describe("prefill", () => {
  it("maps citizen fields incl. nested paths, skips missing", () => {
    const p = prefill(fields, { full_name: "Dummy A", dob: "1960-01-02", address: { line: "House 1" } });
    expect(p).toEqual({ name: "Dummy A", addr: "House 1", dob: "1960-01-02" });
  });
  it("returns empty without citizen", () => expect(prefill(fields, null)).toEqual({}));
});

describe("validate", () => {
  it("flags required and format errors", () => {
    const e = validate(fields, { name: "", dob: "2020-13-45", ifsc: "abc", acct: "123", rel: "Cat", mobile: "12345" });
    expect(Object.keys(e).sort()).toEqual(["acct", "dob", "ifsc", "mobile", "name", "rel"]);
    expect(e.name).toBe("Required");
  });
  it("passes valid data", () => {
    expect(validate(fields, { name: "A", dob: "1960-01-02", ifsc: "SBIN0001234", acct: "123456789012", rel: "Son", mobile: "9876543210" })).toEqual({});
  });
  it("optional empty is fine", () => expect(validate(fields.filter((f) => !f.required), {})).toEqual({}));
});
