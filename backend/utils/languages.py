"""The 10 languages supported across the debugger, validator and practice mode."""

LANGUAGES = [
    {"id": "python", "label": "Python", "ext": "py", "color": "#3b82f6"},
    {"id": "javascript", "label": "JavaScript", "ext": "js", "color": "#facc15"},
    {"id": "typescript", "label": "TypeScript", "ext": "ts", "color": "#38bdf8"},
    {"id": "java", "label": "Java", "ext": "java", "color": "#fb923c"},
    {"id": "c", "label": "C", "ext": "c", "color": "#94a3b8"},
    {"id": "cpp", "label": "C++", "ext": "cpp", "color": "#818cf8"},
    {"id": "csharp", "label": "C#", "ext": "cs", "color": "#a78bfa"},
    {"id": "go", "label": "Go", "ext": "go", "color": "#22d3ee"},
    {"id": "rust", "label": "Rust", "ext": "rs", "color": "#f97316"},
    {"id": "php", "label": "PHP", "ext": "php", "color": "#c084fc"},
]

LANGUAGE_IDS = {l["id"] for l in LANGUAGES}

# Names people type / tools print -> canonical id
ALIASES = {
    "js": "javascript", "node": "javascript", "nodejs": "javascript",
    "ts": "typescript", "py": "python", "python3": "python",
    "c++": "cpp", "cc": "cpp", "c#": "csharp", "cs": "csharp", "golang": "go", "rs": "rust",
}


def normalize_language(lang: str) -> str:
    lang = (lang or "").strip().lower()
    lang = ALIASES.get(lang, lang)
    return lang if lang in LANGUAGE_IDS else "python"


def strict_language(lang: str) -> str:
    """Like normalize_language but raises ValueError instead of silently defaulting."""
    key = (lang or "").strip().lower()
    key = ALIASES.get(key, key)
    if key not in LANGUAGE_IDS:
        raise ValueError("Unsupported language.")
    return key
