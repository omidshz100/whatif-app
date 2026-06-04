import { Pct } from './Pct.jsx';
import { WhyPanel } from './WhyPanel.jsx';
import { IconChevron } from './Icons.jsx';

export function BarChart({ results, openWhy, onToggleWhy, muteOthers = true }) {
  if (!results || results.length === 0) return null;
  const topId = results[0].cause_id;

  // Stable DOM order by cause_id; visual order via CSS `order`
  const rankMap = {};
  results.forEach((r, i) => { rankMap[r.cause_id] = i; });
  const stable = [...results].sort((a, b) => a.cause_id < b.cause_id ? -1 : 1);

  return (
    <div className="chart">
      {stable.map(r => {
        const isTop = r.cause_id === topId;
        const open = openWhy === r.cause_id;
        const fillClass = isTop ? 'top' : (muteOthers ? 'muted' : 'solid');
        return (
          <div
            className={`bar-block${isTop ? ' is-top' : ''}`}
            key={r.cause_id}
            style={{ order: rankMap[r.cause_id] }}
          >
            <div className="bar-head">
              <span className="bar-label">
                {isTop && <span className="rank-tag">Most likely</span>}
                {r.label}
              </span>
              <button
                className={`why-btn${open ? ' is-open' : ''}`}
                onClick={() => onToggleWhy(r.cause_id)}
              >
                Why? <IconChevron open={open} s={13} />
              </button>
            </div>

            <div className="bar-line">
              <div className="bar-track">
                <div
                  className={`bar-fill ${fillClass}`}
                  style={{ width: `${Math.max(2, r.p * 100)}%` }}
                />
              </div>
              <Pct value={r.p} className={`bar-pct${isTop ? ' top' : ''}`} />
            </div>

            {open && <WhyPanel result={r} isTop={isTop} />}
          </div>
        );
      })}
    </div>
  );
}
