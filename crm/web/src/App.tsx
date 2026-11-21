import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";
import Cases from "./pages/Cases";
import NewCase from "./pages/NewCase";
import CaseDetail from "./pages/CaseDetail";

function Login() {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [err, setErr] = useState("");
  return (
    <main><div className="card"><h1>Sign in</h1>
      <form onSubmit={async (e) => { e.preventDefault(); const { error } = await supabase.auth.signInWithPassword({ email, password }); setErr(error?.message ?? ""); }}>
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        <button>Sign in</button>{err && <p className="err">{err}</p>}
      </form></div></main>
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
  return (
    <>
      <div className="banner">DUMMY DATA · NOTHING IS SUBMITTED TO REAL PORTALS</div>
      {session === undefined ? null : !session ? <Login /> : (
        <>
          <header><b>Akshaya-Access CRM</b><a href="#/">Cases</a><a href="#/new">New case</a><span className="sp" />
            <span>{session.user.email}</span><button className="sec" onClick={() => supabase.auth.signOut()}>Sign out</button></header>
          <main>{hash === "#/new" ? <NewCase /> : m ? <CaseDetail id={m[1]} /> : <Cases />}</main>
        </>
      )}
    </>
  );
}
