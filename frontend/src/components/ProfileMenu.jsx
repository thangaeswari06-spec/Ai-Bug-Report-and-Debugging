import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Settings, History, LogOut, ChevronDown } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import Avatar from "./Avatar";

export default function ProfileMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const esc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, []);

  const go = (path) => { setOpen(false); navigate(path); };

  return (
    <div className="relative" ref={box}>
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 rounded-full pl-1 pr-2 py-1 transition hover:bg-white/5" aria-haspopup="menu" aria-expanded={open} aria-label="Open profile menu">
        <Avatar user={user} size={34} />
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} style={{ color: "var(--muted)" }} />
      </button>

      {open && (
        <div className="popover w-64 p-2" role="menu">
          <div className="flex items-center gap-3 p-3">
            <Avatar user={user} size={44} />
            <div className="min-w-0">
              <p className="font-semibold text-sm truncate">{user.name}</p>
              <p className="text-xs truncate" style={{ color: "var(--muted)" }}>{user.email}</p>
            </div>
          </div>
          <div className="h-px my-1" style={{ background: "var(--border)" }} />
          <button role="menuitem" className="menu-item" onClick={() => go("/settings")}><Settings className="w-4 h-4" /> Settings</button>
          <button role="menuitem" className="menu-item" onClick={() => go("/history")}><History className="w-4 h-4" /> History</button>
          <div className="h-px my-1" style={{ background: "var(--border)" }} />
          <button role="menuitem" className="menu-item danger" onClick={() => { setOpen(false); logout(); navigate("/login"); }}><LogOut className="w-4 h-4" /> Log out</button>
        </div>
      )}
    </div>
  );
}
