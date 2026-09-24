const COLORS = { LOW: "#34d399", MEDIUM: "#fbbf24", HIGH: "#fb923c", CRITICAL: "#fb7185" };

export default function SeverityBadge({ severity }) {
  const key = (severity || "").toUpperCase();
  const c = COLORS[key] || "#94a3b8";
  return (
    <span
      className="chip"
      style={{ color: c, borderColor: `color-mix(in srgb, ${c} 45%, transparent)`, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: c, boxShadow: `0 0 8px ${c}` }} />
      {key || "UNKNOWN"}
    </span>
  );
}
