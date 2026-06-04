export function IconPlus({ s = 16 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 3.2v9.6M3.2 8h9.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function IconArrow({ dir = 'up', s = 13 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true"
      style={{ transform: `rotate(${dir === 'up' ? 0 : 180}deg)` }}>
      <path d="M8 12.5V3.5M4.2 7.3L8 3.5l3.8 3.8" stroke="currentColor"
        strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconChevron({ open, s = 14 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true"
      style={{ transition: 'transform .2s ease', transform: open ? 'rotate(180deg)' : 'rotate(0)' }}>
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconHelp({ s = 14 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6.4" stroke="currentColor" strokeWidth="1.3" />
      <path d="M6.4 6.2c0-.9.7-1.6 1.6-1.6s1.6.6 1.6 1.5c0 1.2-1.5 1.2-1.6 2.4"
        stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <circle cx="8" cy="11.2" r=".85" fill="currentColor" />
    </svg>
  );
}

export function IconGear({ s = 16 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="2.4" stroke="currentColor" strokeWidth="1.4" />
      <path d="M8 1.5v1.2M8 13.3v1.2M1.5 8h1.2M13.3 8h1.2M3.4 3.4l.85.85M11.75 11.75l.85.85M3.4 12.6l.85-.85M11.75 4.25l.85-.85"
        stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function IconSend({ s = 14 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M14 8L2 2l3 6-3 6 12-6z" stroke="currentColor" strokeWidth="1.5"
        strokeLinejoin="round" />
    </svg>
  );
}

export function IconSpinner({ s = 14 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true"
      style={{ animation: 'spin 0.8s linear infinite' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.8"
        strokeDasharray="25 13" strokeLinecap="round" />
    </svg>
  );
}
