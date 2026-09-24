import { useEffect, useRef, useState } from "react";
import { ImageUp, ScanText, X, Wand2 } from "lucide-react";
import { extractTextFromImage, errorMessage } from "../services/api";

const MAX_MB = 5;

/**
 * Upload / drag-drop / paste an error screenshot -> OCR on the server ->
 * choose where the extracted text goes (error, stack trace or code).
 */
export default function ImageDropzone({ onUseAsError, onUseAsTrace, onUseAsCode, onLanguageGuess }) {
  const [preview, setPreview] = useState(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");
  const input = useRef(null);

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const handle = async (file) => {
    if (!file) return;
    setErr(""); setResult(null);
    if (!/^image\/(png|jpe?g|webp)$/.test(file.type)) return setErr("Please choose a PNG, JPEG or WebP screenshot.");
    if (file.size > MAX_MB * 1024 * 1024) return setErr(`That image is over ${MAX_MB} MB.`);
    setPreview(URL.createObjectURL(file));
    setBusy(true);
    try {
      const data = await extractTextFromImage(file);
      setResult(data);
      if (data.language_guess) onLanguageGuess?.(data.language_guess);
    } catch (e) { setErr(errorMessage(e)); }
    finally { setBusy(false); }
  };

  // Ctrl+V a screenshot anywhere on the page
  useEffect(() => {
    const onPaste = (e) => {
      const f = [...(e.clipboardData?.files || [])].find((x) => x.type.startsWith("image/"));
      if (f) handle(f);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });

  const reset = () => { setPreview(null); setResult(null); setErr(""); if (input.current) input.current.value = ""; };

  return (
    <div className="space-y-3">
      {!preview ? (
        <label
          className={`dropzone ${drag ? "drag" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files?.[0]); }}
        >
          <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => handle(e.target.files?.[0])} />
          <ImageUp className="w-7 h-7" style={{ color: "var(--a2)" }} />
          <span className="font-semibold text-sm">Upload an error screenshot</span>
          <span className="text-xs" style={{ color: "var(--muted)" }}>Drag & drop, click to browse, or paste with Ctrl+V · PNG / JPG / WebP · max {MAX_MB} MB</span>
        </label>
      ) : (
        <div className="glass p-3 space-y-3 fade-in">
          <div className={`scan-frame ${busy ? "scanning" : ""}`}>
            <img src={preview} alt="Error screenshot preview" className="w-full max-h-56 object-contain bg-black/40" />
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs flex items-center gap-1.5" style={{ color: "var(--muted)" }}>
              {busy ? <><span className="spinner" /> Reading text from the image…</> : <><ScanText className="w-4 h-4" /> {result ? `${result.chars} characters detected` : "Could not read text"}</>}
            </span>
            <button type="button" onClick={reset} className="btn btn-ghost btn-sm"><X className="w-3.5 h-3.5" /> Remove</button>
          </div>

          {result && (
            <div className="space-y-2">
              <pre className="code-view p-3 text-xs max-h-40 overflow-auto whitespace-pre-wrap" style={{ color: "#cbd5e1" }}>{result.text}</pre>
              {result.language_guess && (
                <p className="text-xs flex items-center gap-1.5" style={{ color: "var(--a2)" }}><Wand2 className="w-3.5 h-3.5" /> Looks like {result.language_guess} — language switched for you.</p>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn btn-primary btn-sm" onClick={() => onUseAsError(result.suggested_error)}>Use as error message</button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => onUseAsTrace(result.text)}>Use as stack trace</button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => onUseAsCode(result.text)}>Use as code</button>
              </div>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>OCR can misread characters — check the text before analysing.</p>
            </div>
          )}
        </div>
      )}
      {err && <p className="text-sm" style={{ color: "var(--danger)" }} role="alert">{err}</p>}
    </div>
  );
}
