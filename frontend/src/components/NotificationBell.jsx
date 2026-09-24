import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, ShieldAlert, Sparkles, Trophy, PartyPopper, Trash2, CheckCheck } from "lucide-react";
import { fetchNotifications, markAllRead, clearNotifications } from "../services/api";

const ICONS = { security: ShieldAlert, analysis: Sparkles, practice: Trophy, welcome: PartyPopper };
const COLORS = { security: "#fbbf24", analysis: "var(--a2)", practice: "#34d399", welcome: "var(--a1)" };

function timeAgo(iso) {
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso)) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ unread: 0, items: [] });
  const [ring, setRing] = useState(false);
  const prevUnread = useRef(0);
  const box = useRef(null);

  const load = useCallback(async () => {
    try {
      const d = await fetchNotifications();
      if (d.unread > prevUnread.current) { setRing(true); setTimeout(() => setRing(false), 1300); }
      prevUnread.current = d.unread;
      setData(d);
    } catch { /* ignore - offline */ }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    const onRefresh = () => load();
    window.addEventListener("bf:notify", onRefresh); // pages fire this after actions that create notifications
    return () => { clearInterval(t); window.removeEventListener("bf:notify", onRefresh); };
  }, [load]);

  useEffect(() => {
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const esc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, []);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next) await load();
  };
  const readAll = async () => { await markAllRead(); prevUnread.current = 0; load(); };
  const clear = async () => { await clearNotifications(); prevUnread.current = 0; load(); };

  return (
    <div className="relative" ref={box}>
      <button onClick={toggle} className="btn btn-ghost relative !p-2.5" aria-label={`Notifications${data.unread ? `, ${data.unread} unread` : ""}`} aria-expanded={open}>
        <Bell className={`w-[18px] h-[18px] ${ring ? "ring-bell" : ""}`} />
        {data.unread > 0 && <span className="badge-dot">{data.unread > 9 ? "9+" : data.unread}</span>}
      </button>

      {open && (
        <div className="popover w-[22rem] max-w-[92vw]">
          <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <span className="font-semibold text-sm">Notifications</span>
            <div className="flex gap-1">
              <button onClick={readAll} className="btn btn-ghost btn-sm" title="Mark all as read"><CheckCheck className="w-3.5 h-3.5" /></button>
              <button onClick={clear} className="btn btn-ghost btn-sm" title="Clear all"><Trash2 className="w-3.5 h-3.5" /></button>
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto p-2">
            {data.items.length === 0 && <p className="text-sm text-center py-8" style={{ color: "var(--muted)" }}>You're all caught up 🎉</p>}
            {data.items.map((n) => {
              const Icon = ICONS[n.kind] || Bell;
              return (
                <div key={n.id} className="flex gap-3 p-3 rounded-xl" style={{ background: n.is_read ? "transparent" : "rgb(255 255 255 / .05)" }}>
                  <span className="mt-0.5 shrink-0" style={{ color: COLORS[n.kind] || "var(--muted)" }}><Icon className="w-4 h-4" /></span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium leading-snug">{n.title}</p>
                    {n.body && <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{n.body}</p>}
                    <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>{timeAgo(n.created_at)}</p>
                  </div>
                  {!n.is_read && <span className="ml-auto mt-1.5 w-2 h-2 rounded-full shrink-0" style={{ background: "var(--a2)" }} />}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
