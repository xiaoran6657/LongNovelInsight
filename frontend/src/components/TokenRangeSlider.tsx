import { useState, useRef, useCallback, useEffect } from "react";

function adaptiveStep(min: number, max: number): number {
  const range = max - min;
  if (range <= 1024) return 32;
  if (range <= 4096) return 64;
  if (range <= 16384) return 128;
  return 256;
}

interface Props {
  value: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
  onCommit?: (v: number) => void;
  disabled?: boolean;
  recommendedValue?: number;
  label?: string;
}

export default function TokenRangeSlider({
  value, min = 512, max = 16384,
  onChange, onCommit, disabled,
  recommendedValue, label,
}: Props) {
  const [editText, setEditText] = useState(String(value));
  const [error, setError] = useState("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const holdRef = useRef(0);
  const step = adaptiveStep(min, max);

  // Sync external value changes
  useEffect(() => {
    setEditText(String(value));
    setError("");
  }, [value]);

  const clamp = useCallback((v: number) => Math.max(min, Math.min(max, v)), [min, max]);

  function commitText(raw: string) {
    const v = Number(raw);
    if (isNaN(v) || v < min || v > max) {
      setError(`Must be ${min}–${max}`);
      setEditText(String(value));
      return;
    }
    setError("");
    const c = clamp(v);
    onChange(c);
    if (onCommit) onCommit(c);
  }

  function startAdjust(direction: 1 | -1) {
    holdRef.current = Date.now();
    onChange(clamp(value + direction * step));
    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - holdRef.current;
      let s = step;
      if (elapsed > 3000) s = 100;
      else if (elapsed > 1000) s = 10;
      onChange(clamp(value + direction * s));
    }, 60);
  }

  function stopAdjust() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (onCommit) onCommit(value);
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  return (
    <div style={{ fontSize: "0.82rem" }}>
      {label && <div style={{ marginBottom: "0.15rem", fontWeight: 600 }}>{label}</div>}
      <div style={{ display: "flex", gap: 4, alignItems: "center", marginBottom: "0.25rem" }}>
        <span className="text-dim" style={{ fontSize: "0.7rem" }}>{min}</span>
        <button
          onMouseDown={() => startAdjust(-1)} onMouseUp={stopAdjust} onMouseLeave={stopAdjust}
          disabled={disabled} tabIndex={-1} style={{ padding: "0 4px", fontSize: "0.7rem" }}>▼</button>
        <input
          type="text" value={editText}
          onChange={(e) => { setEditText(e.target.value); setError(""); }}
          onBlur={() => commitText(editText)}
          onKeyDown={(e) => { if (e.key === "Enter") commitText(editText); }}
          disabled={disabled}
          style={{ width: 70, textAlign: "center", fontSize: "0.85rem", fontWeight: 600 }}
          aria-label={label || "Max tokens"}
        />
        <button
          onMouseDown={() => startAdjust(1)} onMouseUp={stopAdjust} onMouseLeave={stopAdjust}
          disabled={disabled} tabIndex={-1} style={{ padding: "0 4px", fontSize: "0.7rem" }}>▲</button>
        <span className="text-dim" style={{ fontSize: "0.7rem" }}>{max}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={clamp(value)}
        onChange={(e) => { const v = Number(e.target.value); onChange(v); }}
        onMouseUp={() => { if (onCommit) onCommit(value); }}
        disabled={disabled}
        style={{ width: "100%", margin: 0 }}
        aria-label={label || "Max tokens slider"}
      />
      {recommendedValue !== undefined && (
        <p className="text-dim" style={{ fontSize: "0.7rem", marginTop: "0.1rem" }}>
          Recommended: {recommendedValue}
        </p>
      )}
      {error && <p className="field-error" style={{ fontSize: "0.7rem", margin: "0.1rem 0" }}>{error}</p>}
    </div>
  );
}
