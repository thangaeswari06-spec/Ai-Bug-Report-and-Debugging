import { useRef, useState } from "react";
import { Camera, Trash2, User, Palette, Lock, ShieldCheck, TriangleAlert, Loader2, Check } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import * as api from "../services/api";
import Avatar from "../components/Avatar";
import LanguagePicker from "../components/LanguagePicker";
import Toast from "../components/Toast";

const ACCENTS = [
  ["violet", "linear-gradient(135deg,#8b5cf6,#22d3ee)"],
  ["cyan", "linear-gradient(135deg,#06b6d4,#3b82f6)"],
  ["emerald", "linear-gradient(135deg,#10b981,#a3e635)"],
  ["rose", "linear-gradient(135deg,#f43f5e,#f59e0b)"],
  ["amber", "linear-gradient(135deg,#f59e0b,#ef4444)"],
];

function Card({ icon: Icon, title, desc, children, danger }) {
  return (
    <section className={`glass p-6 space-y-5 slide-up ${danger ? "" : ""}`} style={danger ? { borderColor: "color-mix(in srgb, var(--danger) 35%, transparent)" } : undefined}>
      <div>
        <h2 className="flex items-center gap-2 text-lg font-bold"><Icon className="w-5 h-5" style={{ color: danger ? "var(--danger)" : "var(--a2)" }} /> {title}</h2>
        {desc && <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>{desc}</p>}
      </div>
      {children}
    </section>
  );
}

export default function SettingsPage() {
  const { user, setUser, logout } = useAuth();
  const [toast, setToast] = useState(null);
  const say = (message, type = "ok") => setToast({ message, type });
  const fileInput = useRef(null);

  // profile
  const [name, setName] = useState(user.name);
  const [savingName, setSavingName] = useState(false);
  // password
  const [pw, setPw] = useState({ current: "", next: "" });
  const [savingPw, setSavingPw] = useState(false);
  // danger
  const [confirmEmail, setConfirmEmail] = useState("");

  const guard = async (fn, okMsg) => {
    try { const r = await fn(); if (okMsg) say(okMsg); return r; }
    catch (e) { say(api.errorMessage(e), "error"); }
  };

  const saveName = async (e) => {
    e.preventDefault();
    setSavingName(true);
    const u = await guard(() => api.updateProfile({ name }), "Name updated");
    if (u) setUser(u);
    setSavingName(false);
  };
  const onAvatar = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) return say("Image is over 2 MB.", "error");
    const u = await guard(() => api.uploadAvatar(file), "Profile picture updated");
    if (u) setUser(u);
  };
  const dropAvatar = async () => { const u = await guard(api.removeAvatar, "Profile picture removed"); if (u) setUser(u); };
  const setPref = async (patch, msg) => { const u = await guard(() => api.updateProfile(patch), msg); if (u) setUser(u); };

  const savePassword = async (e) => {
    e.preventDefault();
    setSavingPw(true);
    const ok = await guard(() => api.changePassword({ current_password: user.has_password ? pw.current : null, new_password: pw.next }), "Password updated");
    if (ok) { setPw({ current: "", next: "" }); setUser({ ...user, has_password: true }); window.dispatchEvent(new Event("bf:notify")); }
    setSavingPw(false);
  };

  const clearAll = async () => {
    if (!confirm("Delete all of your analysis history?")) return;
    await guard(api.clearHistory, "History cleared");
  };
  const removeAccount = async () => {
    const ok = await guard(() => api.deleteAccount(confirmEmail));
    if (ok) logout();
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <h1 className="text-3xl font-extrabold slide-up"><span className="gradient-text">Settings</span></h1>

      <Card icon={User} title="Profile" desc="Your name and picture appear in the top-right menu.">
        <div className="flex flex-wrap items-center gap-5">
          <Avatar user={user} size={84} />
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <button onClick={() => fileInput.current?.click()} className="btn btn-primary btn-sm"><Camera className="w-4 h-4" /> Upload photo</button>
              {user.avatar && <button onClick={dropAvatar} className="btn btn-ghost btn-sm"><Trash2 className="w-4 h-4" /> Remove</button>}
            </div>
            <p className="text-xs" style={{ color: "var(--muted)" }}>PNG, JPG or WebP · max 2 MB · cropped to a square</p>
            <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={onAvatar} />
          </div>
        </div>
        <form onSubmit={saveName} className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
          <div><label className="field-label" htmlFor="pname">Display name</label><input id="pname" className="input" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} /></div>
          <button className="btn btn-primary" disabled={savingName || !name.trim() || name === user.name}>{savingName ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save</button>
        </form>
        <div><span className="field-label">Email</span><p className="text-sm">{user.email} {user.has_google && <span className="chip ml-2">Google linked</span>}</p></div>
      </Card>

      <Card icon={Palette} title="Preferences" desc="Saved to your account.">
        <div><span className="field-label">Default language</span>
          <LanguagePicker value={user.default_language} onChange={(l) => setPref({ default_language: l }, "Default language saved")} /></div>
        <div><span className="field-label">Accent colour</span>
          <div className="flex gap-3" role="radiogroup" aria-label="Accent colour">
            {ACCENTS.map(([id, bg]) => (
              <button key={id} role="radio" aria-checked={user.accent === id} aria-label={id} onClick={() => setPref({ accent: id }, "Accent updated")}
                className="w-10 h-10 rounded-full transition-transform hover:scale-110 grid place-items-center" style={{ background: bg, boxShadow: user.accent === id ? "0 0 0 3px var(--bg), 0 0 0 5px #fff" : "none" }}>
                {user.accent === id && <Check className="w-4 h-4 text-white" />}
              </button>
            ))}
          </div></div>
      </Card>

      <Card icon={Lock} title="Security" desc={user.has_password ? "Change your password." : "You signed in with Google. Set a password to also sign in with email."}>
        <form onSubmit={savePassword} className="space-y-3 max-w-md">
          {user.has_password && <div><label className="field-label" htmlFor="cur">Current password</label><input id="cur" type="password" className="input" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></div>}
          <div><label className="field-label" htmlFor="new">New password</label><input id="new" type="password" className="input" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} placeholder="8+ chars, upper, lower, number" /></div>
          <button className="btn btn-primary" disabled={savingPw || !pw.next || (user.has_password && !pw.current)}>{savingPw && <Loader2 className="w-4 h-4 animate-spin" />} Update password</button>
        </form>
        <ul className="text-sm space-y-1.5" style={{ color: "var(--muted)" }}>
          {["Passwords are salted and hashed (PBKDF2-SHA256) — never stored in plain text", "Sessions expire automatically and are verified on every request", "Repeated wrong passwords lock the account for 10 minutes", "Your history and practice progress are private to your account"].map((t) => (
            <li key={t} className="flex gap-2"><ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" style={{ color: "var(--ok)" }} /> {t}</li>))}
        </ul>
      </Card>

      <Card icon={TriangleAlert} title="Danger zone" danger>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <p className="text-sm">Delete all saved analysis history.</p>
          <button onClick={clearAll} className="btn btn-danger btn-sm"><Trash2 className="w-4 h-4" /> Clear history</button>
        </div>
        <div className="h-px" style={{ background: "var(--border)" }} />
        <div className="space-y-2">
          <p className="text-sm">Permanently delete your account and everything in it. Type <strong>{user.email}</strong> to confirm.</p>
          <div className="flex gap-2 flex-wrap"><input className="input flex-1 min-w-[12rem]" value={confirmEmail} onChange={(e) => setConfirmEmail(e.target.value)} placeholder={user.email} aria-label="Confirm email" />
            <button onClick={removeAccount} disabled={confirmEmail.trim().toLowerCase() !== user.email} className="btn btn-danger">Delete account</button></div>
        </div>
      </Card>

      <Toast toast={toast} onDone={() => setToast(null)} />
    </div>
  );
}
