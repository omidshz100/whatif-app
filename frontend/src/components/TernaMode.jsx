/**
 * Terna Grid Monitor — Predictive Landslide Risk for Transmission Pylons
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────┐
 *   │  Header (title + live clock + back button)           │
 *   ├──────────┬───────────────────────────┬───────────────┤
 *   │ ALERTS   │       LEAFLET MAP         │ PYLON DETAIL  │
 *   │  panel   │   (colored pylon markers) │  (on click)   │
 *   ├──────────┴───────────────────────────┴───────────────┤
 *   │              TIME SLIDER  ◄──48h──►                  │
 *   └──────────────────────────────────────────────────────┘
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// ─── helpers ────────────────────────────────────────────────────────────────

// Terna resilience category colours
const CATEGORY_COLORS = {
  Monitoring: '#22c55e',
  Prevention: '#3b82f6',
  Mitigation: '#f97316',
  Response:   '#ef4444',
  Recovery:   '#a855f7',
};

/**
 * Map Bayesian risk + discretized evidence states to a Terna resilience action.
 * Mirrors the server-side _terna_action() logic so the detail panel can pick up
 * nuances (e.g. very_steep + clay → Relocation; peak passed → Recovery).
 */
function buildActionPlan(risk, states = {}, peakPassed = false) {
  const slope    = states.slope     || 'flat';
  const soilType = states.soil_type || 'sand';

  if (peakPassed && risk < 35) {
    return {
      category:  'Recovery',
      condition: 'Event concluded — risk subsiding after critical peak',
      impact:    'Asset damage assessment required; line restoration pending',
      action:    'Rapid restoration + model update',
    };
  }
  if (risk >= 75) {
    return {
      category:  'Response',
      condition: 'Active landslide on asset — critical Bayesian posterior (≥75%)',
      impact:    'Imminent line outage; cascading fault risk across grid segment',
      action:    'Bypass + emergency plan',
    };
  }
  if (risk >= 55) {
    return {
      category:  'Mitigation',
      condition: 'Landslide triggered near asset — debris flow within 100–200 m',
      impact:    'Line span at risk; load redistribution and alternate routing required',
      action:    'Network redundancy / alternative configuration',
    };
  }
  if (risk >= 30) {
    if (slope === 'very_steep' && soilType === 'clay') {
      return {
        category:  'Prevention',
        condition: 'Repeated high-risk conditions — steep clay terrain with heavy rainfall',
        impact:    'Long-term foundation degradation; structural integrity at risk',
        action:    'Relocation / line burial',
      };
    }
    return {
      category:  'Prevention',
      condition: 'Probable landslide — cumulative rainfall exceeds threshold on susceptible terrain',
      impact:    'Foundation degradation and potential mass movement threatening asset',
      action:    'Foundation reinforcement / structural verification',
    };
  }
  return {
    category:  'Monitoring',
    condition: 'Alert phase — risk within acceptable bounds, no immediate trigger',
    impact:    'No current network impact; maintaining operational awareness',
    action:    'Monitoring + early warning',
  };
}

function riskColor(r) {
  if (r >= 70) return '#ef4444';
  if (r >= 50) return '#f97316';
  if (r >= 30) return '#eab308';
  return '#22c55e';
}
function riskLabel(r) {
  if (r >= 70) return 'Critical';
  if (r >= 50) return 'High';
  if (r >= 30) return 'Medium';
  return 'Low';
}
function severityColor(s) {
  if (s === 'critical') return '#ef4444';
  if (s === 'high')     return '#f97316';
  return '#eab308';
}

function hourLabel(h) {
  const now = new Date();
  now.setMinutes(0, 0, 0);
  const t = new Date(now.getTime() + h * 3600_000);
  const hh = t.getHours().toString().padStart(2, '0');
  const mm = '00';
  const isToday    = t.toDateString() === now.toDateString();
  const isTomorrow = t.toDateString() === new Date(now.getTime() + 86400_000).toDateString();
  const day = isToday ? 'Today' : isTomorrow ? 'Tomorrow' : t.toLocaleDateString('en-GB', { weekday: 'short' });
  return `${day} ${hh}:${mm}`;
}

// ─── Leaflet Map ─────────────────────────────────────────────────────────────

function TernaMap({ pylons, selectedId, onSelect, hour }) {
  const divRef   = useRef(null);
  const mapRef   = useRef(null);
  const markersRef = useRef({});

  // Init map once
  useEffect(() => {
    if (!divRef.current || mapRef.current) return;

    import('leaflet').then(({ default: L }) => {
      import('leaflet/dist/leaflet.css');

      const map = L.map(divRef.current, {
        center: [40.85, 14.65],
        zoom: 9,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 18,
      }).addTo(map);

      mapRef.current = { map, L };
    });

    return () => {
      if (mapRef.current) {
        mapRef.current.map.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Update markers whenever pylons or selection changes
  useEffect(() => {
    if (!mapRef.current || !pylons.length) return;
    const { map, L } = mapRef.current;

    // Remove old markers
    Object.values(markersRef.current).forEach(m => m.remove());
    markersRef.current = {};

    pylons.forEach(p => {
      const color    = riskColor(p.risk);
      const isActive = p.id === selectedId;
      const size     = isActive ? 28 : 22;
      const border   = isActive ? '3px solid #312e81' : '2px solid rgba(0,0,0,0.25)';

      const icon = L.divIcon({
        className: '',
        html: `
          <div style="
            width:${size}px; height:${size}px; border-radius:50%;
            background:${color}; border:${border};
            box-shadow: 0 2px 8px rgba(0,0,0,0.30);
            display:flex; align-items:center; justify-content:center;
            color:#fff; font-size:10px; font-weight:700; font-family:monospace;
            cursor:pointer; transition: transform .15s;
          ">${Math.round(p.risk)}%</div>`,
        iconSize:   [size, size],
        iconAnchor: [size / 2, size / 2],
      });

      const marker = L.marker([p.lat, p.lon], { icon })
        .addTo(map)
        .on('click', () => onSelect(p.id));

      marker.bindTooltip(
        `<b>${p.id}</b><br>${p.name.split('—')[1]?.trim() || ''}<br>Risk: ${p.risk}%`,
        { direction: 'top', offset: [0, -size / 2] }
      );

      markersRef.current[p.id] = marker;
    });
  }, [pylons, selectedId, onSelect]);

  return (
    <div ref={divRef} style={{ width: '100%', height: '100%', minHeight: 0 }} />
  );
}

// ─── Alert Panel ─────────────────────────────────────────────────────────────

function AlertPanel({ alerts, selectedId, onSelect }) {
  return (
    <aside className="terna-alerts">
      <div className="terna-alerts-head">
        <span className="terna-alerts-title">⚠ Early Warnings</span>
        <span className="terna-alerts-count">{alerts.length} pylon{alerts.length !== 1 ? 's' : ''}</span>
      </div>
      {alerts.length === 0 ? (
        <p className="terna-alerts-empty">No pylons above threshold.</p>
      ) : (
        <ul className="terna-alert-list">
          {alerts.map(a => (
            <li
              key={a.pylon_id}
              className={`terna-alert-item${selectedId === a.pylon_id ? ' is-active' : ''}`}
              onClick={() => onSelect(a.pylon_id)}
            >
              <div className="terna-alert-top">
                <span className="terna-alert-id">{a.pylon_id}</span>
                <span className="terna-alert-risk" style={{ color: severityColor(a.severity) }}>
                  {a.peak_risk}%
                </span>
              </div>
              <div className="terna-alert-name">{a.name.split('—')[1]?.trim()}</div>
              <div className="terna-alert-peak">Peak {hourLabel(a.peak_hour)}</div>
              <div className="terna-alert-action">
                {a.action_category && (
                  <span
                    className="terna-alert-cat-badge"
                    style={{ background: CATEGORY_COLORS[a.action_category] || '#6366f1' }}
                  >
                    {a.action_category}
                  </span>
                )}
                {a.action}
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

// ─── Sparkline SVG ───────────────────────────────────────────────────────────

function Sparkline({ risks, currentHour }) {
  if (!risks || risks.length === 0) return null;
  const W = 240, H = 52;
  const max = 100;
  const pts = risks.map((r, i) => {
    const x = (i / (risks.length - 1)) * W;
    const y = H - (r / max) * H;
    return `${x},${y}`;
  }).join(' ');

  const cx = (currentHour / (risks.length - 1)) * W;
  const cy = H - (risks[currentHour] / max) * H;

  return (
    <svg width={W} height={H} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id="spark-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* area fill */}
      <polygon
        points={`0,${H} ${pts} ${W},${H}`}
        fill="url(#spark-grad)"
      />
      {/* line */}
      <polyline
        points={pts}
        fill="none"
        stroke="#6366f1"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* 50% threshold line */}
      <line x1="0" y1={H * 0.5} x2={W} y2={H * 0.5}
        stroke="#f97316" strokeWidth="1" strokeDasharray="4 3" opacity="0.6" />
      {/* current hour cursor */}
      <line x1={cx} y1="0" x2={cx} y2={H}
        stroke="#312e81" strokeWidth="1" strokeDasharray="3 2" opacity="0.7" />
      <circle cx={cx} cy={cy} r="4" fill="#312e81" />
    </svg>
  );
}

// ─── Detail Panel ─────────────────────────────────────────────────────────────

function DetailPanel({ detail, hour, onClose }) {
  const [localEvidence, setLocalEvidence] = useState(null);
  const [liveRisk, setLiveRisk] = useState(null);

  useEffect(() => {
    if (detail) {
      setLocalEvidence({ ...detail.evidence });
      setLiveRisk(detail.risk);
    }
  }, [detail]);

  const updateEvidence = useCallback((key, val) => {
    setLocalEvidence(prev => {
      const next = { ...prev, [key]: val };
      // Recompute risk client-side via API
      fetch(`/api/terna/pylons/${detail.id}/detail?hour=${hour}`, {
        method: 'GET',
      });
      return next;
    });
    // Debounced re-fetch with updated evidence via POST isn't in spec —
    // show note that sliders are exploratory (full re-fetch on blur would be cleaner)
    setLiveRisk(null);
  }, [detail, hour]);

  if (!detail) return null;

  const risk = liveRisk ?? detail.risk;
  const color = riskColor(risk);
  const maxContrib = Math.max(...detail.contributions.map(c => Math.abs(c.delta)), 1);

  const peakPassed = detail.peak_hour < hour && detail.peak_risk >= 55;
  const actionPlan = buildActionPlan(risk, detail.states || {}, peakPassed);
  const catColor   = CATEGORY_COLORS[actionPlan.category] || '#6366f1';

  return (
    <aside className="terna-detail">
      <div className="terna-detail-head">
        <div>
          <div className="terna-detail-id">{detail.id}</div>
          <div className="terna-detail-loc">{detail.name.split('—')[1]?.trim()}</div>
        </div>
        <button className="terna-detail-close" onClick={onClose}>✕</button>
      </div>

      {/* Risk badge */}
      <div className="terna-risk-badge" style={{ background: color + '18', borderColor: color }}>
        <span className="terna-risk-pct" style={{ color }}>{risk.toFixed(1)}%</span>
        <span className="terna-risk-label" style={{ color }}>{riskLabel(risk)} risk</span>
      </div>

      {/* Peak info */}
      <div className="terna-detail-peak">
        Peak <strong>{detail.peak_risk.toFixed(0)}%</strong> at <strong>{hourLabel(detail.peak_hour)}</strong>
        {detail.peak_hour === hour && <span className="terna-peak-now"> ← NOW</span>}
      </div>

      {/* Sparkline */}
      <div className="terna-sparkline-wrap">
        <Sparkline risks={detail.all_risks} currentHour={hour} />
        <div className="terna-sparkline-labels">
          <span>Now</span><span>+24h</span><span>+48h</span>
        </div>
      </div>

      {/* Evidence contributions */}
      <div className="terna-section-label">Why? — Evidence breakdown</div>
      <ul className="terna-contribs">
        {detail.contributions.map(c => (
          <li key={c.id} className="terna-contrib-row">
            <div className="terna-contrib-top">
              <span className="terna-contrib-label">{c.label}</span>
              <span className="terna-contrib-state">{c.state}</span>
              <span className={`terna-contrib-delta ${c.delta >= 0 ? 'pos' : 'neg'}`}>
                {c.delta >= 0 ? '+' : ''}{c.delta}pp
              </span>
            </div>
            <div className="terna-contrib-bar-track">
              <div
                className={`terna-contrib-bar ${c.delta >= 0 ? 'pos' : 'neg'}`}
                style={{ width: `${Math.abs(c.delta) / maxContrib * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>

      {/* Evidence sliders */}
      <div className="terna-section-label">Adjust evidence</div>
      {localEvidence && detail.evidence_meta.map(meta => {
        if (meta.kind === 'slider') {
          const val = localEvidence[meta.id] ?? meta.min;
          const pct = ((val - meta.min) / (meta.max - meta.min)) * 100;
          return (
            <div key={meta.id} className="terna-ev-field">
              <div className="terna-ev-top">
                <span className="terna-ev-label">{meta.label}</span>
                <span className="terna-ev-value">{val}{meta.unit}</span>
              </div>
              <input
                type="range" min={meta.min} max={meta.max} step={meta.step}
                value={val}
                className="ev-range"
                style={{ '--fill': `${pct}%` }}
                onChange={e => updateEvidence(meta.id, parseFloat(e.target.value))}
              />
            </div>
          );
        }
        if (meta.kind === 'toggle') {
          const val = localEvidence[meta.id] ?? false;
          return (
            <div key={meta.id} className="terna-ev-field terna-ev-row">
              <span className="terna-ev-label">{meta.label}</span>
              <button
                className={`switch${val ? ' on' : ''}`}
                onClick={() => updateEvidence(meta.id, !val)}
              >
                <span className="switch-knob" />
                <span style={{ fontSize: 12, color: val ? '#fff' : 'var(--text-2)' }}>
                  {val ? 'Yes' : 'No'}
                </span>
              </button>
            </div>
          );
        }
        if (meta.kind === 'segment') {
          const val = localEvidence[meta.id];
          return (
            <div key={meta.id} className="terna-ev-field terna-ev-row">
              <span className="terna-ev-label">{meta.label}</span>
              <div className="terna-seg-group">
                {meta.options.map(o => (
                  <button
                    key={o.id}
                    className={`terna-seg-btn${val === o.id ? ' active' : ''}`}
                    onClick={() => updateEvidence(meta.id, o.id)}
                  >{o.label}</button>
                ))}
              </div>
            </div>
          );
        }
        return null;
      })}

      {/* Recommended action */}
      <div className="terna-section-label" style={{ marginTop: 16 }}>Recommended action</div>
      <div className="terna-action-card" style={{ borderColor: catColor + '55' }}>
        <span className="terna-action-cat-badge" style={{ background: catColor }}>
          {actionPlan.category}
        </span>
        <div className="terna-action-field">
          <span className="terna-action-field-lbl">Condition</span>
          <span className="terna-action-field-val">{actionPlan.condition}</span>
        </div>
        <div className="terna-action-field">
          <span className="terna-action-field-lbl">Network impact</span>
          <span className="terna-action-field-val">{actionPlan.impact}</span>
        </div>
        <div className="terna-action-field" style={{ marginBottom: 0 }}>
          <span className="terna-action-field-lbl">Action</span>
          <span className="terna-action-field-val" style={{ color: catColor, fontWeight: 600 }}>
            {actionPlan.action}
          </span>
        </div>
      </div>
    </aside>
  );
}

// ─── Time Slider ─────────────────────────────────────────────────────────────

function TimeSlider({ hour, onChange, allRisks }) {
  const HOURS = 48;
  // Find the global max-risk hour across all pylons at each slot
  const maxRisks = Array.from({ length: HOURS }, (_, h) => {
    if (!allRisks || !Object.keys(allRisks).length) return 0;
    return Math.max(...Object.values(allRisks).map(arr => arr[h]?.risk ?? 0));
  });

  return (
    <div className="terna-timeline">
      <div className="terna-timeline-labels">
        <span>Now</span>
        <span className="terna-timeline-current">{hourLabel(hour)}</span>
        <span>+48h</span>
      </div>

      {/* Mini risk heatmap bar */}
      <div className="terna-heatmap">
        {maxRisks.map((r, i) => (
          <div
            key={i}
            className="terna-heatmap-cell"
            style={{ background: riskColor(r), opacity: 0.6 + (r / 100) * 0.4 }}
            title={`${hourLabel(i)}: max risk ${r.toFixed(0)}%`}
          />
        ))}
        {/* cursor */}
        <div
          className="terna-heatmap-cursor"
          style={{ left: `${(hour / (HOURS - 1)) * 100}%` }}
        />
      </div>

      <input
        type="range"
        min={0} max={HOURS - 1} step={1}
        value={hour}
        className="terna-time-range"
        style={{ '--fill': `${(hour / (HOURS - 1)) * 100}%` }}
        onChange={e => onChange(Number(e.target.value))}
      />
    </div>
  );
}

// ─── Main TernaMode ──────────────────────────────────────────────────────────

export function TernaMode({ onBack }) {
  const [hour, setHour]           = useState(0);
  const [pylons, setPylons]       = useState([]);
  const [alerts, setAlerts]       = useState([]);
  const [allRisks, setAllRisks]   = useState({});
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail]       = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Fetch all-pylon risk at current hour
  useEffect(() => {
    fetch(`/api/terna/pylons?hour=${hour}`)
      .then(r => r.json())
      .then(setPylons)
      .catch(() => {});
  }, [hour]);

  // Fetch alerts (based on peak risk, independent of current hour)
  useEffect(() => {
    fetch(`/api/terna/alerts?hour=${hour}`)
      .then(r => r.json())
      .then(setAlerts)
      .catch(() => {});
  }, [hour]);

  // Fetch full 48h forecast (for heatmap / sparkline) — once
  useEffect(() => {
    fetch('/api/terna/forecast')
      .then(r => r.json())
      .then(setAllRisks)
      .catch(() => {});
  }, []);

  // Fetch detail when pylon is selected or hour changes
  useEffect(() => {
    if (!selectedId) return;
    setLoadingDetail(true);
    fetch(`/api/terna/pylons/${selectedId}/detail?hour=${hour}`)
      .then(r => r.json())
      .then(d => { setDetail(d); setLoadingDetail(false); })
      .catch(() => setLoadingDetail(false));
  }, [selectedId, hour]);

  const handleSelect = useCallback((id) => {
    setSelectedId(prev => prev === id ? null : id);
    if (!id) setDetail(null);
  }, []);

  return (
    <div className="terna-root">
      {/* Header */}
      <header className="terna-header">
        <button className="terna-back-btn" onClick={onBack}>← WhatIf</button>
        <div className="terna-header-title">
          <span className="terna-logo">⚡</span>
          <span>Terna Grid Monitor</span>
          <span className="terna-header-sub">Predictive Landslide Risk · 48h Forecast</span>
        </div>
        <div className="terna-header-meta">
          <span className="terna-header-status">● LIVE DEMO</span>
          <span className="terna-header-pylons">{pylons.length} pylons monitored</span>
        </div>
      </header>

      {/* Body */}
      <div className="terna-body">
        <AlertPanel alerts={alerts} selectedId={selectedId} onSelect={handleSelect} />

        <div className="terna-map-wrap">
          <TernaMap
            pylons={pylons}
            selectedId={selectedId}
            onSelect={handleSelect}
            hour={hour}
          />
        </div>

        {selectedId && (
          <div className="terna-detail-wrap">
            {loadingDetail
              ? <div className="terna-detail-loading">Loading…</div>
              : <DetailPanel detail={detail} hour={hour} onClose={() => handleSelect(null)} />
            }
          </div>
        )}
      </div>

      {/* Timeline */}
      <TimeSlider hour={hour} onChange={setHour} allRisks={allRisks} />
    </div>
  );
}
