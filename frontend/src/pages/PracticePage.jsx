import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Trophy, CheckCircle2, Swords } from "lucide-react";
import { fetchProblems, errorMessage } from "../services/api";
import { LANGUAGES } from "../utils/languages";

const DIFF_COLOR = { Easy: "#34d399", Medium: "#fbbf24", Hard: "#fb7185" };

export default function PracticePage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("All");

  useEffect(() => { fetchProblems().then(setData).catch((e) => setErr(errorMessage(e))); }, []);

  const problems = useMemo(() => (data?.problems || []).filter((p) => filter === "All" || p.difficulty === filter), [data, filter]);
  const pct = data ? Math.round((data.stats.solved / data.stats.total) * 100) : 0;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <div className="glass gradient-border p-6 flex flex-wrap items-center justify-between gap-6 slide-up">
        <div className="space-y-2">
          <h1 className="text-3xl font-extrabold flex items-center gap-3"><Swords className="w-7 h-7" style={{ color: "var(--a2)" }} /> <span className="gradient-text">Practice arena</span></h1>
          <p className="text-sm max-w-lg" style={{ color: "var(--muted)" }}>Solve problems in any of 10 languages. Stuck or getting an error? One click sends your code to the AI BugFixer to find the broken line.</p>
          <div className="flex flex-wrap gap-1.5 pt-1">{LANGUAGES.map((l) => <span key={l.id} className="chip" style={{ "--c": l.color }}><span className="w-1.5 h-1.5 rounded-full" style={{ background: l.color }} />{l.label}</span>)}</div>
        </div>
        {data && (
          <div className="flex items-center gap-4">
            <div className="ring" style={{ "--p": pct, "--size": "5.5rem" }}><span className="font-bold">{data.stats.solved}/{data.stats.total}</span></div>
            <div className="text-sm space-y-1"><p className="flex items-center gap-1.5 font-semibold"><Trophy className="w-4 h-4" style={{ color: "#fbbf24" }} /> Solved</p>
              <p style={{ color: "var(--muted)" }}>{data.stats.languages_used} language{data.stats.languages_used === 1 ? "" : "s"} used</p></div>
          </div>
        )}
      </div>

      <div className="flex gap-2">
        {["All", "Easy", "Medium"].map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={`chip lang-chip ${filter === f ? "on" : ""}`}>{f}</button>
        ))}
      </div>

      {err && <p style={{ color: "var(--danger)" }} className="text-sm">{err}</p>}
      {!data && !err && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="skeleton h-40" />)}</div>}

      <div className="problem-grid">
        <div className="inner">
          {problems.map((p, i) => {
            const solved = p.solved_languages.length > 0;
            return (
              <Link key={p.id} to={`/practice/${p.id}`} className="glass card-hover p-5 flex flex-col gap-3 slide-up" style={{ "--i": Math.min(i, 9) }}>
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-bold text-lg leading-snug">{p.title}</h2>
                  {solved && <CheckCircle2 className="w-5 h-5 shrink-0" style={{ color: "var(--ok)" }} aria-label="Solved" />}
                </div>
                <p className="text-sm line-clamp-2" style={{ color: "var(--muted)" }}>{p.statement.replace(/`/g, "")}</p>
                <div className="flex items-center gap-2 mt-auto flex-wrap">
                  <span className="chip" style={{ color: DIFF_COLOR[p.difficulty], borderColor: `color-mix(in srgb, ${DIFF_COLOR[p.difficulty]} 45%, transparent)` }}>{p.difficulty}</span>
                  <span className="chip">{p.topic}</span>
                  {p.solved_languages.slice(0, 4).map((l) => <span key={l} className="chip on">{LANGUAGES.find((x) => x.id === l)?.label}</span>)}
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
