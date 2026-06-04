export function ExplanationPanel({ computed }) {
  if (!computed?.biggest_driver) return null;
  const { biggest_driver: bd } = computed;
  const before = bd.before;
  const after = bd.after;
  const dpp = Math.round(bd.delta * 100);
  const dropping = bd.delta < 0;

  return (
    <section className="explain">
      <div className="explain-tag">What-If · biggest driver</div>
      <div className="explain-body">
        <p className="explain-lead">
          <strong>{bd.lever_verb}</strong> ({bd.lever_detail}) — and{' '}
          <span className="explain-cause">{bd.top_label}</span> moves from{' '}
          <span className="explain-num">{Math.round(before * 100)}%</span> to{' '}
          <span className="explain-num accent">{Math.round(after * 100)}%</span>{' '}
          <span className={`explain-delta ${dropping ? 'down' : 'up'}`}>
            {dpp > 0 ? '+' : '−'}{Math.abs(dpp)}pp
          </span>.
        </p>
        <p className="explain-note">
          {dropping
            ? "That's the single biggest change you can make to this result — the strongest lever on your top suspected cause."
            : "This action would actually raise the likelihood — not the lever to pull here."}
        </p>
        {computed.llm_summary && (
          <p className="explain-llm">"{computed.llm_summary}"</p>
        )}
      </div>
    </section>
  );
}
