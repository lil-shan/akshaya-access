export const STATUSES = ["draft", "ready", "running", "waiting_citizen", "done", "failed", "cancelled"];
export const STATUS_LABEL: Record<string, string> = { draft: "Draft", ready: "Ready", running: "Running", waiting_citizen: "Waiting for citizen", done: "Done", failed: "Failed", cancelled: "Cancelled" };
export const TIER_LABEL: Record<string, string> = { pdf: "PDF", mock_portal: "Portal", portal_dry_run: "Dry run on real portal", api: "API" };
export const Status = ({ s }: { s: string }) => <span className={`badge ${s}`}>{STATUS_LABEL[s] ?? s}</span>;
export const Tier = ({ t }: { t: string }) => <span className={`tier ${t}`}>{TIER_LABEL[t] ?? t}</span>;
export const when = (iso: string) => new Date(iso).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
