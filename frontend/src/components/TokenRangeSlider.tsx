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
  const valueRef = useRef(value);
  const step = adaptiveStep(min, max);

  // Sync ref + editText when value changes externally
  useEffect(() => {
    valueRef.current = value;
    setEditText(String(value));
    setError("");
  }, [value]);

  const clamp = useCallback((v: number) => Math.max(min, Math.min(max, v)), [min, max]);

  function commitText(raw: string) {
    const v = Number(raw);
    if (isNaN(v) || v < min || v > max) {
      setError(`Must be ${min}–${max}`);
      setEditText(String(valueRef.current));
      return;
    }
    setError("");
    const c = clamp(v);
    valueRef.current = c;
    onChange(c);
    if (onCommit) onCommit(c);
  }

  function startAdjust(direction: 1 | -1) {
    holdRef.current = Date.now();
    const next = clamp(valueRef.current + direction * step);
    valueRef.current = next;
    onChange(next);
    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - holdRef.current;
      let s = step;
      if (elapsed > 3000) s = 100;
      else if (elapsed > 1000) s = 10;
      const nextVal = clamp(valueRef.current + direction * s);
      valueRef.current = nextVal;
      onChange(nextVal);
    }, 60);
  }

  function stopAdjust() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (onCommit) onCommit(valueRef.current);
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  return (
    <div style={{ fontSize: "0.82rem" }}>
      {label && <div style={{ marginBottom: "0.15rem", fontWeight: 600 }}>{label}</div>}
      <div style={{ display: "flex", gap: 4, alignItems: "center", marginBottom: "0.25rem" }}>
        <input
          type="text" value={String(min)}
          readOnly
          style={{ width: 55, textAlign: "center", fontSize: "0.72rem", background: "#f5f5f5" }}
          aria-label="Min tokens"
        />
        <button
          onMouseDown={() => startAdjust(-1)} onMouseUp={stopAdjust} onMouseLeave={stopAdjust} onTouchStart={() => startAdjust(-1)} onTouchEnd={stopAdjust}
          disabled={disabled} style={{ padding: "0 4px", fontSize: "0.7rem" }}>▼</button>
        <input
          type="text" value={editText}
          onChange={(e) => { setEditText(e.target.value); setError(""); }}
          onBlur={() => commitText(editText)}
          onKeyDown={(e) => { if (e.key === "Enter") commitText(editText); }}
          disabled={disabled}
          style={{ width: 70, textAlign: "center", fontSize: "0.85rem", fontWeight: 600 }}
          aria-label={label || "Max tokens value"}
        />
        <button
          onMouseDown={() => startAdjust(1)} onMouseUp={stopAdjust} onMouseLeave={stopAdjust} onTouchStart={() => startAdjust(1)} onTouchEnd={stopAdjust}
          disabled={disabled} style={{ padding: "0 4px", fontSize: "0.7rem" }}>▲</button>
        <input
          type="text" value={String(max)}
          readOnly
          style={{ width: 55, textAlign: "center", fontSize: "0.72rem", background: "#f5f5f5" }}
          aria-label="Max tokens"
        />
      </div>
      <input
        type="range" min={min} max={max} step={step} value={clamp(value)}
        onChange={(e) => { const v = Number(e.target.value); valueRef.current = v; onChange(v); }}
        onMouseUp={() => { if (onCommit) onCommit(valueRef.current); }}
        onTouchEnd={() => { if (onCommit) onCommit(valueRef.current); }}
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
