import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Play, Send, CheckCircle2, XCircle, Loader2, Bug, Clock, PartyPopper } from "lucide-react";
import { fetchProblem, fetchPracticeLanguages, runPractice, submitPractice, analyzeBug, errorMessage } from "../services/api";
import { useAuth } from "../context/AuthContext";
import CodeEditor from "../components/CodeEditor";
import LanguagePicker from "../components/LanguagePicker";
import ResultCard from "../components/ResultCard";

export default function PracticeProblemPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [language, setLanguage] = useState(user?.default_language || "python");
  const [problem, setProblem] = useState(null);
  const [runnable, setRunnable] = useState({});
  const [codes, setCodes] = useState({});           // remembers your code per language
  const [outcome, setOutcome] = useState(null);
  const [busy, setBusy] = useState("");             // "run" | "submit" | "ai"
  const [err, setErr] = useState("");
  const [ai, setAi] = useState(null);
  const [aiCode, setAiCode] = useState("");
  const starters = useRef({});

  useEffect(() => { fetchPracticeLanguages().then((l) => setRunnable(Object.fromEntries(l.map((x) => [x.id, x.runnable])))).catch(() => {}); }, []);

  useEffect(() => {
    setOutcome(null); setAi(null); setErr("");
    fetchProblem(id, language).then((p) => {
      setProblem(p);
      starters.current[language] = p.starter;
      setCodes((c) => (c[language] === undefined ? { ...c, [language]: p.starter } : c));
    }).catch((e) => setErr(errorMessage(e)));
  }, [id, language]);

  const code = codes[language] ?? "";
  const setCode = (v) => setCodes((c) => ({ ...c, [language]: v }));
  const notRunnable = runnable[language] === false;

  const exec = async (kind) => {
    setErr(""); setBusy(kind); setAi(null);
    try {
      const fn = kind === "run" ? runPractice : submitPractice;
      const res = await fn({ problem_id: id, language, code });
      setOutcome({ ...res, kind });
      if (kind === "submit") window.dispatchEvent(new Event("bf:notify"));
    } catch (e) { setErr(errorMessage(e)); }
    finally { setBusy(""); }
  };

  const askAI = async () => {
    if (!outcome) return;
    let error = "", trace = "";
    if (outcome.status === "compile_error") { error = outcome.message.split("\n").slice(0, 6).join("\n"); trace = outcome.message; }
    else {
      const bad = outcome.results.find((r) => !r.passed);
      if (!bad) return;
      if (bad.stderr) { error = bad.stderr.split("\n").filter(Boolean).slice(-3).join("\n"); trace = bad.stderr; }
      else if (bad.status === "timeout") error = "Time limit exceeded - the program ran too long (possible infinite loop).";
      else error = `Wrong answer on test ${bad.index}. Input: ${bad.input ?? "(hidden)"} | Expected: ${bad.expected ?? "(hidden)"} | Got: ${bad.actual ?? ""}`;
    }
    setBusy("ai");
    try {
      setAiCode(code);
      setAi(await analyzeBug({ language, code, error, stackTrace: trace }));
      window.dispatchEvent(new Event("bf:notify"));
    } catch (e) { setErr(errorMessage(e)); }
    finally { setBusy(""); }
  };

  const failed = outcome && (outcome.status === "compile_error" || !outcome.all_passed);

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-5">
      <Link to="/practice" className="btn btn-ghost btn-sm w-fit"><ArrowLeft className="w-4 h-4" /> All problems</Link>

      {!problem && !err && <div className="skeleton h-64" />}
      {problem && (
        <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 items-start">
          {/* ---- statement ---- */}
          <section className="glass p-6 space-y-4 slide-up lg:sticky lg:top-24">
            <div className="flex flex-wrap items-center gap-2"><span className="chip on">{problem.difficulty}</span><span className="chip">{problem.topic}</span><span className="chip">{problem.total_tests} tests</span></div>
            <h1 className="text-2xl font-extrabold">{problem.title}</h1>
            <p className="leading-relaxed" style={{ color: "#c4cbe0" }}>{problem.statement.split("`").map((part, i) => i % 2 ? <code key={i} className="px-1.5 py-0.5 rounded" style={{ background: "rgb(255 255 255 / .1)", color: "var(--a2)" }}>{part}</code> : part)}</p>
            <div className="space-y-3">
              {problem.examples.map((ex, i) => (
                <div key={i} className="code-view p-3 text-xs space-y-1">
                  <p style={{ color: "var(--muted)" }}>Example {i + 1}</p>
                  <p><span style={{ color: "var(--muted)" }}>Input </span><span className="font-mono whitespace-pre-wrap">{ex.input}</span></p>
                  <p><span style={{ color: "var(--muted)" }}>Output </span><span className="font-mono whitespace-pre-wrap" style={{ color: "#a7f3d0" }}>{ex.output}</span></p>
                </div>
              ))}
            </div>
            <p className="text-xs" style={{ color: "var(--muted)" }}>Read from standard input, print to standard output. Hidden tests run when you Submit.</p>
          </section>

          {/* ---- workspace ---- */}
          <section className="space-y-4 slide-up" style={{ "--i": 1 }}>
            <div className="glass p-5 space-y-4">
              <LanguagePicker value={language} onChange={setLanguage} disabledIds={Object.keys(runnable).filter((k) => runnable[k] === false)} hint={Object.fromEntries(Object.keys(runnable).filter((k) => runnable[k] === false).map((k) => [k, "Compiler/runtime not installed on the server"]))} />
              {notRunnable && <p className="text-xs rounded-lg px-3 py-2" style={{ color: "#fde68a", background: "rgb(251 191 36 / .1)", border: "1px solid rgb(251 191 36 / .3)" }}>The {language} toolchain isn't installed on this server. Install it (see README) or pick another language.</p>}
              <CodeEditor label="Your solution" value={code} onChange={setCode} rows={14} />
              <div className="flex flex-wrap gap-2">
                <button onClick={() => exec("run")} disabled={!!busy || notRunnable || !code.trim()} className="btn btn-ghost">
                  {busy === "run" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Run examples</button>
                <button onClick={() => exec("submit")} disabled={!!busy || notRunnable || !code.trim()} className="btn btn-primary">
                  {busy === "submit" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Submit</button>
                <button onClick={() => setCode(starters.current[language] || "")} className="btn btn-ghost ml-auto btn-sm self-center">Reset code</button>
              </div>
              {err && <p className="text-sm" role="alert" style={{ color: "var(--danger)" }}>{err}</p>}
            </div>

            {outcome && (
              <div className="glass p-5 space-y-3 fade-in" aria-live="polite">
                {outcome.all_passed ? (
                  <p className="flex items-center gap-2 font-bold text-lg" style={{ color: "var(--ok)" }}><PartyPopper className="w-5 h-5" /> {outcome.kind === "submit" ? "Accepted — all tests passed!" : "Example tests passed!"}
                    {outcome.first_solve && <span className="chip on ml-2">First solve 🎉</span>}</p>
                ) : outcome.status === "compile_error" ? (
                  <><p className="flex items-center gap-2 font-bold" style={{ color: "var(--danger)" }}><XCircle className="w-5 h-5" /> Compile error</p>
                    <pre className="code-view p-3 text-xs overflow-auto max-h-56 whitespace-pre-wrap" style={{ color: "#fecdd3" }}>{outcome.message}</pre></>
                ) : (
                  <p className="flex items-center gap-2 font-bold" style={{ color: "var(--danger)" }}><XCircle className="w-5 h-5" /> {outcome.passed}/{outcome.total} tests passed</p>
                )}

                {outcome.status === "ok" && (
                  <div className="space-y-2">
                    {outcome.results.map((r) => (
                      <div key={r.index} className="rounded-xl p-3 text-xs" style={{ background: "rgb(0 0 0 / .3)", border: `1px solid ${r.passed ? "color-mix(in srgb, var(--ok) 35%, transparent)" : "color-mix(in srgb, var(--danger) 35%, transparent)"}` }}>
                        <div className="flex items-center justify-between font-semibold text-sm">
                          <span className="flex items-center gap-1.5">{r.passed ? <CheckCircle2 className="w-4 h-4" style={{ color: "var(--ok)" }} /> : <XCircle className="w-4 h-4" style={{ color: "var(--danger)" }} />} Test {r.index}{r.hidden && <span className="chip">hidden</span>}</span>
                          {r.status === "timeout" && <span className="flex items-center gap-1" style={{ color: "var(--warn)" }}><Clock className="w-3.5 h-3.5" /> timeout</span>}
                        </div>
                        {!r.hidden && !r.passed && (
                          <div className="mt-2 font-mono space-y-1">
                            <p><span style={{ color: "var(--muted)" }}>input: </span>{r.input}</p>
                            <p><span style={{ color: "var(--muted)" }}>expected: </span><span style={{ color: "#a7f3d0" }}>{r.expected}</span></p>
                            <p><span style={{ color: "var(--muted)" }}>got: </span><span style={{ color: "#fecdd3" }}>{r.actual || "(nothing printed)"}</span></p>
                          </div>
                        )}
                        {r.stderr && !r.passed && <pre className="mt-2 whitespace-pre-wrap max-h-32 overflow-auto" style={{ color: "#fecdd3" }}>{r.stderr}</pre>}
                      </div>
                    ))}
                  </div>
                )}

                {failed && (
                  <button onClick={askAI} disabled={busy === "ai"} className="btn btn-primary btn-sm">
                    {busy === "ai" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bug className="w-4 h-4" />} Ask AI BugFixer where it went wrong</button>
                )}
              </div>
            )}

            {ai && <ResultCard result={ai} originalCode={aiCode} />}
          </section>
        </div>
      )}
    </div>
  );
}
