import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";
import Dashboard from "./pages/Dashboard";
import Cases from "./pages/Cases";
import NewCase from "./pages/NewCase";
import CaseDetail from "./pages/CaseDetail";

function Login() {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [err, setErr] = useState("");
  return (
    <div className="login"><div className="card"><h1>Akshaya-Access</h1><p className="ml">Remote Akshaya centre · അക്ഷയ കേന്ദ്രം</p>
      <form onSubmit={async (e) => { e.preventDefault(); const { error } = await supabase.auth.signInWithPassword({ email, password }); setErr(error?.message ?? ""); }}>
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        <button>Sign in</button>{err && <p className="err">{err}</p>}
      </form></div></div>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    const h = () => setHash(location.hash); addEventListener("hashchange", h);
    return () => { data.subscription.unsubscribe(); removeEventListener("hashchange", h); };
  }, []);
  const m = hash.match(/^#\/case\/(.+)$/);
  const nav = (h: string, on: boolean, t: string) => <a href={h} className={on ? "on" : ""} aria-current={on ? "page" : undefined}>{t}</a>;
  return (
    <>
      <div className="banner">DUMMY DATA · NOTHING IS SUBMITTED TO REAL PORTALS</div>
      {session === undefined ? null : !session ? <Login /> : (
        <div className="shell">
          <nav className="side"><div className="brand">Akshaya-Access</div><div className="brand-ml">അക്ഷയ-ആക്സസ്</div>
            {nav("#/", hash === "" || hash === "#/" || hash === "#", "Today")}
            {nav("#/cases", hash.startsWith("#/cases"), "All cases")}
            {nav("#/new", hash === "#/new", "New case")}
            <span className="sp" /><span className="who">{session.user.email}</span>
            <button onClick={() => supabase.auth.signOut()}>Sign out</button></nav>
          <main>{hash === "#/new" ? <NewCase /> : m ? <CaseDetail id={m[1]} /> : hash.startsWith("#/cases") ? <Cases /> : <Dashboard />}</main>
        </div>
      )}
    </>
  );
}
