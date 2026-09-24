import { LANGUAGES } from "../utils/languages";

export default function LanguagePicker({ value, onChange, disabledIds = [], hint = {} }) {
  return (
    <div role="radiogroup" aria-label="Programming language" className="flex flex-wrap gap-2">
      {LANGUAGES.map((l) => (
        <button
          key={l.id}
          type="button"
          role="radio"
          aria-checked={value === l.id}
          title={hint[l.id] || l.label}
          onClick={() => onChange(l.id)}
          className="chip lang-chip"
          style={{ "--c": l.color, opacity: disabledIds.includes(l.id) ? 0.55 : 1 }}
        >
          <span className="dot" />
          {l.label}
        </button>
      ))}
    </div>
  );
}
