import { useState, useEffect, useRef } from 'react';

function useCountUp(target, dur = 420) {
  const [val, setVal] = useState(target);
  const stateRef = useRef({ raf: 0, to: 0, fallback: 0 });

  useEffect(() => {
    const from = val;
    const to = target;
    stateRef.current.to = to;
    if (Math.abs(from - to) < 1e-5) { setVal(to); return; }
    cancelAnimationFrame(stateRef.current.raf);
    clearTimeout(stateRef.current.fallback);
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(from + (to - from) * eased);
      if (t < 1) stateRef.current.raf = requestAnimationFrame(tick);
      else setVal(to);
    };
    stateRef.current.raf = requestAnimationFrame(tick);
    stateRef.current.fallback = setTimeout(() => setVal(stateRef.current.to), dur + 120);
    return () => {
      cancelAnimationFrame(stateRef.current.raf);
      clearTimeout(stateRef.current.fallback);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, dur]);

  return val;
}

export function Pct({ value, className }) {
  const v = useCountUp(value);
  return (
    <span className={className}>
      {Math.round(v * 100)}<span className="pct-sign">%</span>
    </span>
  );
}
