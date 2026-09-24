import { AlertCircle } from "lucide-react";
import { diffLines } from "../utils/diff";

const SOURCE_LABEL = {
  ai: "AI analysis",
  trace: "error message",
  caller: "call path in the stack trace",
  syntax: "compiler / parser check",
  diff: "changed by the fix",
};

/** Read-only code with the broken lines highlighted and a "why" note under each. */
export function ErrorCodeView({ code, locations = [] }) {
  const byLine = new Map(locations.map((l) => [l.line, l]));
  const rows = code.split("\n");
  return (
    <div className="code-view">
      <div className="scroll py-3">
        {rows.map((text, i) => {
          const loc = byLine.get(i + 1);
          return (
            <div key={i}>
              <div className={`cl ${loc ? "err" : ""}`} id={`err-line-${i + 1}`}>
                <span className="no">{i + 1}</span>
                <span className="mark">{loc ? "▶" : ""}</span>
                <span className="tx">{text || " "}</span>
              </div>
              {loc && (
                <div className="err-note">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <div>
                    <div><strong>Line {loc.line}:</strong> {loc.reason}</div>
                    <div className="mt-1 opacity-70 text-xs">
                      detected by {loc.sources.map((s) => SOURCE_LABEL[s] || s).join(" + ")}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Before/after diff of the AI's fix. */
export function DiffView({ original, corrected }) {
  const rows = diffLines(original, corrected);
  const changed = rows.some((r) => r.type !== "same");
  return (
    <div className="code-view">
      <div className="scroll py-3">
        {rows.map((r, i) => (
          <div key={i} className={`cl ${r.type === "add" ? "add" : r.type === "del" ? "del" : ""}`}>
            <span className="no">{r.newNo ?? r.oldNo}</span>
            <span className="mark">{r.type === "add" ? "+" : r.type === "del" ? "−" : ""}</span>
            <span className="tx">{r.text || " "}</span>
          </div>
        ))}
        {!changed && <p className="px-4 py-2 text-xs" style={{ color: "var(--muted)" }}>No code changes were suggested.</p>}
      </div>
    </div>
  );
}
