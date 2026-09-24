import { useRef } from "react";

/** Textarea with a synced line-number gutter. */
export default function CodeEditor({ value, onChange, rows = 12, placeholder, tone, label }) {
  const gutter = useRef(null);
  const count = Math.max(value.split("\n").length, rows);
  const numbers = Array.from({ length: count }, (_, i) => i + 1).join("\n");

  const onKeyDown = (e) => {
    if (e.key === "Tab") { // keep focus in the editor and insert 4 spaces
      e.preventDefault();
      const el = e.target, { selectionStart: s, selectionEnd: en } = el;
      onChange(value.slice(0, s) + "    " + value.slice(en));
      requestAnimationFrame(() => (el.selectionStart = el.selectionEnd = s + 4));
    }
  };

  return (
    <div className={`editor ${tone === "red" ? "tone-red" : ""}`}>
      <div ref={gutter} className="gutter" aria-hidden="true">{numbers}</div>
      <textarea
        aria-label={label}
        value={value}
        rows={rows}
        spellCheck={false}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onScroll={(e) => { if (gutter.current) gutter.current.scrollTop = e.target.scrollTop; }}
      />
    </div>
  );
}
