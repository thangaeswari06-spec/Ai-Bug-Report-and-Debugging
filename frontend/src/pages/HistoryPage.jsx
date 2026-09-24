import { useEffect, useState } from "react";
import { Trash2, ChevronDown, History as HistoryIcon, MapPin } from "lucide-react";
import { fetchHistory, clearHistory, deleteHistoryItem, errorMessage } from "../services/api";
import SeverityBadge from "../components/SeverityBadge";
import ResultCard from "../components/ResultCard";
import { langLabel } from "../utils/languages";

export default function HistoryPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState(null);
  const [apiError, setApiError] = useState("");

  useEffect(() => {
    (async () => {
      try { setItems(await fetchHistory()); }
      catch (e) { setApiError(errorMessage(e)); }
      finally { setLoading(false); }
    })();
  }, []);

  const handleClear = async () => {
    if (!confirm("Clear all your analysis history? This cannot be undone.")) return;
    await clearHistory();
    setItems([]);
  };
  const handleDelete = async (id) => {
    await deleteHistoryItem(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-5">
      <div className="flex items-center justify-between slide-up">
        <div>
          <h1 className="text-3xl font-extrabold flex items-center gap-3"><HistoryIcon className="w-7 h-7" style={{ color: "var(--a2)" }} /> <span className="gradient-text">History</span></h1>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>Only you can see these reports.</p>
        </div>
        {items.length > 0 && <button onClick={handleClear} className="btn btn-danger btn-sm"><Trash2 className="w-4 h-4" /> Clear all</button>}
      </div>

      {loading && <div className="space-y-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-16" />)}</div>}
      {apiError && <p style={{ color: "var(--danger)" }} className="text-sm">{apiError}</p>}
      {!loading && !items.length && !apiError && (
        <div className="glass p-12 text-center" style={{ color: "var(--muted)" }}>No analyses yet. Run one from the Debugger and it will show up here.</div>
      )}

      <div className="space-y-3">
        {items.map((item, idx) => {
          const open = openId === item.id;
          const first = item.error_locations?.[0];
          return (
            <div key={item.id} className="glass overflow-hidden slide-up" style={{ "--i": Math.min(idx, 8) }}>
              <button onClick={() => setOpenId(open ? null : item.id)} className="w-full flex items-center justify-between gap-3 px-4 py-3.5 text-left hover:bg-white/5 transition-colors">
                <div className="flex items-center gap-3 min-w-0 flex-wrap">
                  <SeverityBadge severity={item.severity} />
                  <span className="font-semibold truncate">{item.bug_type}</span>
                  <span className="chip">{langLabel(item.language)}</span>
                  {first && <span className="chip"><MapPin className="w-3 h-3" /> line {first.line}</span>}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs hidden sm:inline" style={{ color: "var(--muted)" }}>{new Date(item.created_at).toLocaleString()}</span>
                  <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} style={{ color: "var(--muted)" }} />
                </div>
              </button>
              {open && (
                <div className="p-4 border-t space-y-3 fade-in" style={{ borderColor: "var(--border)" }}>
                  <ResultCard result={item} />
                  <button onClick={() => handleDelete(item.id)} className="btn btn-danger btn-sm"><Trash2 className="w-3.5 h-3.5" /> Delete this report</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
