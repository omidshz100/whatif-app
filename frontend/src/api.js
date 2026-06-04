const BASE = '/api';

async function req(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  listInvestigations:   ()              => req('GET',  '/investigations'),
  getInvestigation:     (id)            => req('GET',  `/investigations/${id}`),
  compute:              (id, evidence)  => req('POST', `/investigations/${id}/compute`, { evidence }),
  extractEvidence:      (id, text)      => req('POST', `/investigations/${id}/extract-evidence`, { text }),
  generateInvestigation:(text)          => req('POST', '/investigations/generate', { problem_text: text }),
  createInvestigation:  (spec)          => req('POST', '/investigations', { spec }),
  getSettings:          ()              => req('GET',  '/settings'),
  saveSettings:         (data)          => req('POST', '/settings', data),
  testConnection:       ()              => req('POST', '/settings/test'),
};

export function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
