import { useEffect, useRef, useState } from "react";
import { Loader2, Sparkles, AlertTriangle, ChevronDown } from "lucide-react";
import { analyzeBug, errorMessage } from "../services/api";
import { useAuth } from "../context/AuthContext";
import ResultCard from "../components/ResultCard";
import CodeEditor from "../components/CodeEditor";
import LanguagePicker from "../components/LanguagePicker";
import ImageDropzone from "../components/ImageDropzone";

const SAMPLES = {
  python: {
    code: 'total = 10\ncount = 0\n\ndef average(t, c):\n    return t / c\n\nprint(average(total, count))\n',
    error: "ZeroDivisionError: division by zero",
    trace: 'Traceback (most recent call last):\n  File "app.py", line 7, in <module>\n    print(average(total, count))\n  File "app.py", line 5, in average\n    return t / c\nZeroDivisionError: division by zero',
  },
  c: {
    code: '#include <stdio.h>\n\nint main(void) {\n    int x = 5\n    printf("%d\\n", x);\n    return 0;\n}\n',
    error: "error: expected ';' before 'printf'",
    trace: "",
  },
  javascript: {
    code: 'const user = { name: "Sam" };\n\nfunction showCity(u) {\n  return u.address.city.toUpperCase();\n}\n\nconsole.log(showCity(user));\n',
    error: "TypeError: Cannot read properties of undefined (reading 'city')",
    trace: "    at showCity (/app/index.js:4:22)\n    at Object.<anonymous> (/app/index.js:7:13)",
  },
  go: {
    code: 'package main\n\nimport "fmt"\n\nfunc main() {\n    nums := []int{1, 2, 3}\n    fmt.Println(nums[5])\n}\n',
    error: "panic: runtime error: index out of range [5] with length 3",
    trace: "main.main()\n\t/app/main.go:7 +0x1d",
  },
};

export default function DebuggerPage() {
  const { user } = useAuth();
  const [language, setLanguage] = useState(user?.default_language || "python");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [stackTrace, setStackTrace] = useState("");
  const [showTrace, setShowTrace] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [submittedCode, setSubmittedCode] = useState("");
  const [apiError, setApiError] = useState("");
  const resultRef = useRef(null);

  useEffect(() => { if (result) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [result]);

  const handleAnalyze = async () => {
    if (!code.trim() || !error.trim()) return setApiError("Please provide both the source code and the error message (or upload a screenshot of it).");
    setApiError(""); setLoading(true); setResult(null);
    try {
      const data = await analyzeBug({ language, code, error, stackTrace });
      setSubmittedCode(code);
      setResult(data);
      window.dispatchEvent(new Event("bf:notify"));
    } catch (err) { setApiError(errorMessage(err)); }
    finally { setLoading(false); }
  };

  const loadSample = () => {
    const key = SAMPLES[language] ? language : "python";
    const s = SAMPLES[key];
    setLanguage(key); setCode(s.code); setError(s.error); setStackTrace(s.trace); setShowTrace(!!s.trace);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 grid lg:grid-cols-2 gap-8 items-start">
      {/* ---- input column ---- */}
      <div className="space-y-5 slide-up">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h1 className="text-3xl font-extrabold"><span className="gradient-text">Analyze</span> a bug</h1>
            <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>Paste code + error, or just upload a screenshot of the error.</p>
          </div>
          <button onClick={loadSample} className="btn btn-ghost btn-sm shrink-0">Load sample</button>
        </div>

        <div className="glass p-5 space-y-5">
          <div>
            <span className="field-label">Language</span>
            <LanguagePicker value={language} onChange={setLanguage} />
          </div>

          <div>
            <span className="field-label">Source code</span>
            <CodeEditor label="Source code" value={code} onChange={setCode} rows={11} placeholder={"Paste the code that is failing…"} />
          </div>

          <div>
            <span className="field-label">Error screenshot <span style={{ textTransform: "none", letterSpacing: 0 }}>(optional)</span></span>
            <ImageDropzone
              onUseAsError={setError}
              onUseAsTrace={(t) => { setStackTrace(t); setShowTrace(true); }}
              onUseAsCode={setCode}
              onLanguageGuess={setLanguage}
            />
          </div>

          <div>
            <label className="field-label" htmlFor="err">Error message</label>
            <textarea id="err" className="input mono" rows={3} value={error} onChange={(e) => setError(e.target.value)} placeholder="e.g. ZeroDivisionError: division by zero" spellCheck={false} style={{ color: "#fecdd3" }} />
          </div>

          <div>
            <button type="button" onClick={() => setShowTrace(!showTrace)} className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--muted)" }}>
              <ChevronDown className={`w-4 h-4 transition-transform ${showTrace ? "rotate-180" : ""}`} /> Stack trace <span className="normal-case tracking-normal font-normal">(optional — improves line detection)</span>
            </button>
            {showTrace && <textarea className="input mono mt-2 fade-in" rows={4} value={stackTrace} onChange={(e) => setStackTrace(e.target.value)} spellCheck={false} aria-label="Stack trace" />}
          </div>

          {apiError && (
            <div className="flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm" role="alert" style={{ color: "#ffe4e6", background: "color-mix(in srgb, var(--danger) 14%, transparent)", border: "1px solid color-mix(in srgb, var(--danger) 35%, transparent)" }}>
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> {apiError}
            </div>
          )}

          <button onClick={handleAnalyze} disabled={loading} className="btn btn-primary w-full !py-3.5 !text-base">
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
            {loading ? "Analyzing…" : "Analyze bug"}
          </button>
        </div>
      </div>

      {/* ---- result column ---- */}
      <div ref={resultRef} className="lg:sticky lg:top-24 scroll-mt-24">
        {!result && !loading && (
          <div className="glass grid place-items-center text-center p-10 min-h-[22rem] gap-3" style={{ borderStyle: "dashed" }}>
            <Sparkles className="w-8 h-8" style={{ color: "var(--a2)" }} />
            <p className="font-semibold">Your debug report appears here</p>
            <p className="text-sm max-w-xs" style={{ color: "var(--muted)" }}>You'll see the exact broken line highlighted, why it fails, and a diff of the fix.</p>
          </div>
        )}
        {loading && (
          <div className="glass p-6 space-y-4" aria-busy="true">
            <div className="flex items-center gap-3 text-sm" style={{ color: "var(--muted)" }}><span className="spinner" /> Classifying, locating the error line, retrieving similar bugs…</div>
            <div className="skeleton h-7 w-2/3" /><div className="skeleton h-4 w-full" /><div className="skeleton h-4 w-5/6" /><div className="skeleton h-40 w-full" />
          </div>
        )}
        {result && !loading && <ResultCard result={result} originalCode={submittedCode} />}
      </div>
    </div>
  );
}
