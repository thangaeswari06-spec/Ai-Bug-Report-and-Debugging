import { useEffect } from "react";
import { CheckCircle2, XCircle } from "lucide-react";

export default function Toast({ toast, onDone }) {
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(onDone, 3500);
    return () => clearTimeout(t);
  }, [toast, onDone]);
  if (!toast) return null;
  return (
    <div className={`toast ${toast.type === "error" ? "bad" : "ok"} flex items-center gap-2`} role="status">
      {toast.type === "error" ? <XCircle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
      {toast.message}
    </div>
  );
}
