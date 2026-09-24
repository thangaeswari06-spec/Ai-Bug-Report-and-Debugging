// Mirrors backend/utils/languages.py
export const LANGUAGES = [
  { id: "python", label: "Python", color: "#3b82f6" },
  { id: "javascript", label: "JavaScript", color: "#facc15" },
  { id: "typescript", label: "TypeScript", color: "#38bdf8" },
  { id: "java", label: "Java", color: "#fb923c" },
  { id: "c", label: "C", color: "#94a3b8" },
  { id: "cpp", label: "C++", color: "#818cf8" },
  { id: "csharp", label: "C#", color: "#a78bfa" },
  { id: "go", label: "Go", color: "#22d3ee" },
  { id: "rust", label: "Rust", color: "#f97316" },
  { id: "php", label: "PHP", color: "#c084fc" },
];
export const langLabel = (id) => LANGUAGES.find((l) => l.id === id)?.label || id;
