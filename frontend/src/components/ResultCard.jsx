import { useState } from "react";
import { Copy, Check, Download, CheckCircle2, XCircle, HelpCircle, RefreshCcw, MapPin, Lightbulb, GitCompare, BookOpen } from "lucide-react";
import SeverityBadge from "./SeverityBadge";
import { ErrorCodeView, DiffView } from "./CodeView";
import { langLabel } from "../utils/languages";

function ValidationBadge({ validation }) {
  if (!validation) return null;
  const map = validation.valid === true
    ? { Icon: CheckCircle2, c: "var(--ok)", t: "Fix validated" }
    : validation.valid === false
      ? { Icon: XCircle, c: "var(--danger)", t: "Fix failed validation" }
      : { Icon: HelpCircle, c: "var(--muted)", t: "Validation skipped" };
  return <span className="inline-flex items-center gap-1.5 text-sm font-medium" style={{ color: map.c }}><map.Icon className="w-4 h-4" /> {map.t}</span>;
}

function Section({ icon: Icon, title, children }) {
  return (
    <div>
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--muted)" }}>
        <Icon className="w-4 h-4" style={{ color: "var(--a2)" }} /> {title}
      </h3>
      {children}
    </div>
  );
}

export default function ResultCard({ result, originalCode }) {
  const [tab, setTab] = useState("where");
  const [copied, setCopied] = useState(false);
  if (!result) return null;

  const original = result.original_code ?? originalCode ?? "";
  const locations = result.error_locations || [];

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result.corrected_code || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleDownload = () => {
    const where = locations.length ? locations.map((l) => `  Line ${l.line}: ${l.text.trim()}\n    -> ${l.reason}`).join("\n") : "  (not detected)";
    const report = `AI BugFixer Report
===================
Language: ${langLabel(result.language)}
Bug Type: ${result.bug_type}
Severity: ${result.severity}
Confidence: ${result.confidence}

Where the error is:
${where}

Root Cause:
${result.root_cause}

Explanation:
${result.explanation}

Recommended Fix:
${result.fix}

Corrected Code:
${result.corrected_code}

Validation: ${result.validation?.message || "N/A"}
`;
    const url = URL.createObjectURL(new Blob([report], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `bugfixer-report-${result.id?.slice(0, 8) || "report"}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const tabs = [
    { id: "where", label: `Error location${locations.length ? ` (${locations.length})` : ""}`, Icon: MapPin },
    { id: "fix", label: "Fix", Icon: GitCompare },
    { id: "similar", label: `Similar bugs (${result.similar_known_bugs?.length || 0})`, Icon: BookOpen },
  ];
  const pct = Math.round((result.confidence || 0) * 100);

  return (
    <div className="glass gradient-border p-5 sm:p-6 space-y-5 fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-bold">{result.bug_type}</h2>
            <SeverityBadge severity={result.severity} />
            <span className="chip">{langLabel(result.language)}</span>
            {result.retried && <span className="chip"><RefreshCcw className="w-3 h-3" /> retried once</span>}
          </div>
          <ValidationBadge validation={result.validation} />
        </div>
        <div className="ring" style={{ "--p": pct, "--size": "4.2rem" }} title={`Classifier confidence ${pct}%`}>
          <span className="text-sm font-bold">{pct}%</span>
        </div>
      </div>

      <Section icon={Lightbulb} title="Why this error happened">
        <p className="font-medium">{result.root_cause || "—"}</p>
        {result.explanation && <p className="text-sm leading-relaxed mt-2" style={{ color: "#b8c0d6" }}>{result.explanation}</p>}
      </Section>

      <div className="flex gap-1 p-1 rounded-xl overflow-x-auto" style={{ background: "rgb(0 0 0 / .3)" }} role="tablist">
        {tabs.map(({ id, label, Icon }) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className="btn btn-sm flex-1 whitespace-nowrap"
            style={tab === id ? { background: "linear-gradient(135deg, color-mix(in srgb, var(--a1) 60%, transparent), color-mix(in srgb, var(--a2) 45%, transparent))", color: "#fff" } : { color: "var(--muted)" }}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {tab === "where" && (
        <Section icon={MapPin} title={locations.length ? "The broken line(s) — and why" : "Error location"}>
          {locations.length ? (
            <ErrorCodeView code={original} locations={locations} />
          ) : (
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              No exact line could be pinned down — the error message has no line number and the code parses cleanly. Include the full stack trace (or upload the screenshot) for a precise line.
            </p>
          )}
        </Section>
      )}

      {tab === "fix" && (
        <div className="space-y-4">
          <Section icon={Lightbulb} title="Recommended fix"><p>{result.fix || "—"}</p></Section>
          <Section icon={GitCompare} title="Changes (red = removed, green = added)">
            <DiffView original={original} corrected={result.corrected_code || ""} />
          </Section>
          <div className="flex flex-wrap gap-2">
            <button onClick={handleCopy} className="btn btn-ghost btn-sm">
              {copied ? <Check className="w-3.5 h-3.5" style={{ color: "var(--ok)" }} /> : <Copy className="w-3.5 h-3.5" />} {copied ? "Copied" : "Copy fixed code"}
            </button>
            <button onClick={handleDownload} className="btn btn-ghost btn-sm"><Download className="w-3.5 h-3.5" /> Download report</button>
          </div>
          {result.validation?.message && <p className="text-xs whitespace-pre-wrap" style={{ color: "var(--muted)" }}>{result.validation.message}</p>}
        </div>
      )}

      {tab === "similar" && (
        <div className="space-y-2">
          {(result.similar_known_bugs || []).map((bug) => (
            <div key={bug.kb_id} className="glass p-3 text-sm">
              <div className="flex justify-between gap-2">
                <span className="font-semibold">{bug.bug_type} <span className="chip ml-1">{langLabel(bug.language)}</span></span>
                <span style={{ color: "var(--muted)" }}>{Math.round(bug.score * 100)}% match</span>
              </div>
              <p className="mt-1" style={{ color: "#b8c0d6" }}>{bug.root_cause}</p>
              <p className="mt-1 text-xs" style={{ color: "var(--ok)" }}>Fix: {bug.fix}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
