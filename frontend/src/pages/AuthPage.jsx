import { useMemo, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { GoogleOAuthProvider, GoogleLogin } from "@react-oauth/google";
import { Bug, Eye, EyeOff, Loader2, Mail, Lock, User, ShieldCheck, ScanSearch, Swords, MapPin } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../services/api";
import Background from "../components/Background";

function strength(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (pw.length >= 12 || /[^A-Za-z0-9]/.test(pw)) s++;
  return pw ? Math.max(1, s) : 0;
}
const STRENGTH_TEXT = ["", "Weak", "Fair", "Good", "Strong"];

function GoogleButton({ config, onCredential, onError }) {
  if (!config.google_enabled) {
    return (
      <div className="w-full">
        <button type="button" className="btn btn-ghost w-full" disabled title="Set GOOGLE_CLIENT_ID on the backend to enable this">
          <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.5 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9c4.4-4.1 7-10.1 7-17.6z"/><path fill="#FBBC05" d="M10.5 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.9-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.8l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.9 2.3-8.3 2.3-6.3 0-11.6-4-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z"/></svg>
          Continue with Google
        </button>
        <p className="text-[11px] mt-1.5 text-center" style={{ color: "var(--muted)" }}>Not configured yet — add <code>GOOGLE_CLIENT_ID</code> to the backend (see README).</p>
      </div>
    );
  }
  return (
    <GoogleOAuthProvider clientId={config.google_client_id}>
      <div className="flex justify-center">
        <GoogleLogin theme="filled_black" shape="pill" size="large" text="continue_with" width="320"
          onSuccess={(res) => onCredential(res.credential)} onError={() => onError("Google sign-in was cancelled or failed.")} />
      </div>
    </GoogleOAuthProvider>
  );
}

const FEATURES = [
  { Icon: MapPin, t: "Pinpoints the exact line", d: "See which line is broken and why." },
  { Icon: ScanSearch, t: "Reads error screenshots", d: "Upload an image — OCR does the typing." },
  { Icon: Swords, t: "Practice in 10 languages", d: "Solve problems and get AI help when stuck." },
];

export default function AuthPage() {
  const { user, booting, config, login, signup, googleLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const score = useMemo(() => strength(form.password), [form.password]);

  if (!booting && user) return <Navigate to={location.state?.from || "/"} replace />;

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const done = () => navigate(location.state?.from || "/", { replace: true });

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      if (mode === "login") await login(form.email, form.password);
      else await signup(form.name, form.email, form.password);
      done();
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  };

  const onGoogle = async (credential) => {
    setError(""); setBusy(true);
    try { await googleLogin(credential); done(); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <Background />

      {/* ---- brand panel ---- */}
      <section className="hidden lg:flex flex-col justify-center px-16 gap-10">
        <div className="flex items-center gap-3 slide-up">
          <span className="grid place-items-center w-12 h-12 rounded-2xl" style={{ background: "linear-gradient(135deg, var(--a1), var(--a2))", boxShadow: "0 12px 40px -10px var(--a1)" }}>
            <Bug className="w-7 h-7 text-white" />
          </span>
          <span className="text-2xl font-bold">AI BugFixer</span>
        </div>
        <h1 className="text-5xl font-extrabold leading-tight slide-up" style={{ "--i": 1 }}>
          Find the bug.<br /><span className="gradient-text">Understand the why.</span>
        </h1>
        <ul className="space-y-5">
          {FEATURES.map(({ Icon, t, d }, i) => (
            <li key={t} className="flex gap-4 slide-up" style={{ "--i": i + 2 }}>
              <span className="glass grid place-items-center w-11 h-11 shrink-0"><Icon className="w-5 h-5" style={{ color: "var(--a2)" }} /></span>
              <div><p className="font-semibold">{t}</p><p className="text-sm" style={{ color: "var(--muted)" }}>{d}</p></div>
            </li>
          ))}
        </ul>
      </section>

      {/* ---- form panel ---- */}
      <section className="flex items-center justify-center p-5">
        <div className="glass gradient-border w-full max-w-md p-7 sm:p-8 space-y-5 slide-up">
          <div className="flex items-center gap-2 lg:hidden font-bold text-lg"><Bug className="w-5 h-5" style={{ color: "var(--a2)" }} /> AI BugFixer</div>

          <div className="flex p-1 rounded-xl" style={{ background: "rgb(0 0 0 / .3)" }} role="tablist">
            {[["login", "Sign in"], ["signup", "Create account"]].map(([id, label]) => (
              <button key={id} role="tab" aria-selected={mode === id} type="button" onClick={() => { setMode(id); setError(""); }}
                className="btn btn-sm flex-1" style={mode === id ? { background: "linear-gradient(135deg, var(--a1), var(--a2))", color: "#fff" } : { color: "var(--muted)" }}>{label}</button>
            ))}
          </div>

          <div>
            <h2 className="text-2xl font-bold">{mode === "login" ? "Welcome back" : "Join AI BugFixer"}</h2>
            <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>{mode === "login" ? "Sign in to continue debugging." : "Create your account — it takes 10 seconds."}</p>
          </div>

          <GoogleButton config={config} onCredential={onGoogle} onError={setError} />

          <div className="flex items-center gap-3 text-xs" style={{ color: "var(--muted)" }}>
            <span className="h-px flex-1" style={{ background: "var(--border)" }} /> or with email <span className="h-px flex-1" style={{ background: "var(--border)" }} />
          </div>

          <form onSubmit={submit} className="space-y-4" noValidate>
            {mode === "signup" && (
              <div>
                <label className="field-label" htmlFor="name">Name</label>
                <div className="relative"><User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
                  <input id="name" className="input !pl-10" value={form.name} onChange={set("name")} placeholder="Your name" autoComplete="name" required maxLength={60} /></div>
              </div>
            )}
            <div>
              <label className="field-label" htmlFor="email">Email</label>
              <div className="relative"><Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
                <input id="email" type="email" className="input !pl-10" value={form.email} onChange={set("email")} placeholder="you@example.com" autoComplete="email" required /></div>
            </div>
            <div>
              <label className="field-label" htmlFor="password">Password</label>
              <div className="relative"><Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
                <input id="password" type={show ? "text" : "password"} className="input !pl-10 !pr-11" value={form.password} onChange={set("password")}
                  placeholder={mode === "signup" ? "8+ chars, upper, lower, number" : "Your password"} autoComplete={mode === "login" ? "current-password" : "new-password"} required />
                <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} aria-label={show ? "Hide password" : "Show password"}>
                  {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button>
              </div>
              {mode === "signup" && (
                <div className="mt-2 space-y-1"><div className="meter" data-s={score}><i /><i /><i /><i /></div>
                  <p className="text-[11px]" style={{ color: "var(--muted)" }}>{score ? `Strength: ${STRENGTH_TEXT[score]}` : "Use 8+ characters with upper & lower case letters and a number."}</p></div>
              )}
            </div>

            {error && <p className="text-sm rounded-lg px-3 py-2" role="alert" style={{ color: "#ffe4e6", background: "color-mix(in srgb, var(--danger) 14%, transparent)", border: "1px solid color-mix(in srgb, var(--danger) 35%, transparent)" }}>{error}</p>}

            <button type="submit" disabled={busy} className="btn btn-primary w-full !py-3">
              {busy && <Loader2 className="w-4 h-4 animate-spin" />}{mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="text-[11px] flex items-center justify-center gap-1.5" style={{ color: "var(--muted)" }}>
            <ShieldCheck className="w-3.5 h-3.5" style={{ color: "var(--ok)" }} /> Passwords are salted + hashed · sessions expire · sign-in attempts are rate-limited
          </p>
        </div>
      </section>
    </div>
  );
}
