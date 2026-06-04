import { IconArrow } from './Icons.jsx';

export function WhyPanel({ result, isTop }) {
  const noContribs = !result.contributions || result.contributions.length === 0;
  return (
    <div className="why-panel">
      <div className="why-row why-base">
        <span className="why-dot why-neutral" />
        <span className="why-text">
          Prior probability for this cause before any evidence is applied.
        </span>
      </div>

      {noContribs && (
        <div className="why-row">
          <span className="why-dot why-neutral" />
          <span className="why-text">No evidence currently moves this either way.</span>
        </div>
      )}

      {(result.contributions || []).map((c, i) => {
        const up = c.delta > 0;
        const absDelta = Math.abs(c.delta);
        return (
          <div className="why-row" key={i}>
            <span className={`why-dot ${up ? 'why-up' : 'why-down'}`}>
              <IconArrow dir={up ? 'up' : 'down'} s={12} />
            </span>
            <span className="why-text">{c.text}</span>
            <span className={`why-delta ${up ? 'is-up' : 'is-down'}`}>
              {up ? '+' : '−'}{(absDelta * 100).toFixed(1)}pp
            </span>
          </div>
        );
      })}

      <div className="why-foot">
        {isTop
          ? 'These signals combine to make this the most likely cause right now.'
          : 'Adjust the evidence on the right to see how this would change.'}
      </div>
    </div>
  );
}
