import { NavLink, Link } from "react-router-dom";
import { Bug, Swords, ScanSearch } from "lucide-react";
import NotificationBell from "./NotificationBell";
import ProfileMenu from "./ProfileMenu";

const link = ({ isActive }) =>
  `btn btn-sm ${isActive ? "" : "btn-ghost"}`;

export default function Navbar() {
  return (
    <header className="sticky top-0 z-30 border-b backdrop-blur-xl" style={{ borderColor: "var(--border)", background: "color-mix(in srgb, var(--bg) 70%, transparent)" }}>
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <Link to="/" className="flex items-center gap-2 font-bold text-lg">
          <span className="grid place-items-center w-9 h-9 rounded-xl" style={{ background: "linear-gradient(135deg, var(--a1), var(--a2))", boxShadow: "0 8px 24px -8px var(--a1)" }}>
            <Bug className="w-5 h-5 text-white" />
          </span>
          <span className="gradient-text hidden sm:inline">AI BugFixer</span>
        </Link>

        <nav className="flex gap-2" aria-label="Main">
          <NavLink to="/" end className={link} style={({ isActive }) => isActive ? { background: "linear-gradient(135deg, var(--a1), var(--a2))", color: "#fff" } : undefined}>
            <ScanSearch className="w-4 h-4" /> <span>Debugger</span>
          </NavLink>
          <NavLink to="/practice" className={link} style={({ isActive }) => isActive ? { background: "linear-gradient(135deg, var(--a1), var(--a2))", color: "#fff" } : undefined}>
            <Swords className="w-4 h-4" /> <span>Practice</span>
          </NavLink>
        </nav>

        <div className="flex items-center gap-2">
          <NotificationBell />
          <ProfileMenu />
        </div>
      </div>
    </header>
  );
}
