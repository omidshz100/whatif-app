import { useState, useEffect, useCallback, useRef } from 'react';
import { api, debounce } from '../api.js';

const LS_KEY = 'whatif_dynamic_specs';
function _loadSavedSpecs() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch { return {}; }
}
function _saveSavedSpec(id, spec) {
  try {
    const all = _loadSavedSpecs();
    localStorage.setItem(LS_KEY, JSON.stringify({ ...all, [id]: spec }));
  } catch {}
}
function _removeSavedSpec(id) {
  try {
    const all = _loadSavedSpecs();
    delete all[id];
    localStorage.setItem(LS_KEY, JSON.stringify(all));
  } catch {}
}

export function useWhatIf() {
  const [investigations, setInvestigations] = useState([]);
  const [activeId, setActiveId] = useState('electricity');
  const [invDetails, setInvDetails] = useState({});
  const [computedByCase, setComputedByCase] = useState({});
  const [valuesByCase, setValuesByCase] = useState({});
  const [openWhy, setOpenWhy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  // Bootstrap on mount
  useEffect(() => {
    async function bootstrap() {
      try {
        let summaries = await api.listInvestigations();

        // Re-create any dynamic investigations saved in localStorage that are
        // missing from the server (serverless functions lose in-memory state).
        const savedSpecs = _loadSavedSpecs();
        const serverIds = new Set(summaries.map(s => s.id));
        for (const [id, spec] of Object.entries(savedSpecs)) {
          if (!serverIds.has(id)) {
            try {
              const inv = await api.createInvestigation(spec);
              summaries = [...summaries, {
                id: inv.id, title: inv.title, subtitle: inv.subtitle,
                is_placeholder: false, top_label: null, top_p: null,
              }];
            } catch (_) {
              // If re-creation fails, remove stale spec from storage.
              _removeSavedSpec(id);
            }
          }
        }

        setInvestigations(summaries);
        setActiveId(summaries[0]?.id || 'electricity');

        // Use allSettled so a single 404 doesn't crash the whole bootstrap.
        const settled = await Promise.allSettled(
          summaries.filter(s => !s.is_placeholder).map(s => api.getInvestigation(s.id))
        );
        const details = settled
          .filter(r => r.status === 'fulfilled')
          .map(r => r.value);

        const detailMap = {};
        const valuesMap = {};
        for (const inv of details) {
          detailMap[inv.id] = inv;
          valuesMap[inv.id] = { ...inv.defaults };
        }
        setInvDetails(detailMap);
        setValuesByCase(valuesMap);

        const results = await Promise.all(
          details.map(inv => api.compute(inv.id, inv.defaults).then(r => ({ id: inv.id, result: r })))
        );
        const computedMap = {};
        for (const { id, result } of results) {
          computedMap[id] = result;
        }
        setComputedByCase(computedMap);
        if (results[0]) setOpenWhy(results[0].result.top.cause_id);
        setLoading(false);
      } catch (e) {
        setError(e.message);
        setLoading(false);
      }
    }
    bootstrap();
  }, []);

  // Debounced recompute when evidence changes
  const computeRef = useRef(null);
  useEffect(() => {
    computeRef.current = debounce(async (invId, evidence) => {
      try {
        const result = await api.compute(invId, evidence);
        setComputedByCase(prev => ({ ...prev, [invId]: result }));
        setInvestigations(prev => prev.map(s =>
          s.id === invId ? { ...s, top_label: result.top.label, top_p: result.top.p } : s
        ));
      } catch (_) {}
    }, 60);
  }, []);

  const setValue = useCallback((evId, val) => {
    setValuesByCase(prev => {
      const updated = { ...prev, [activeId]: { ...prev[activeId], [evId]: val } };
      computeRef.current?.(activeId, updated[activeId]);
      return updated;
    });
  }, [activeId]);

  const selectCase = useCallback((id) => {
    setActiveId(id);
    setWizardOpen(false);
    const result = computedByCase[id];
    setOpenWhy(result ? result.top.cause_id : null);
  }, [computedByCase]);

  const openWizard = useCallback(() => {
    setWizardOpen(true);
  }, []);

  // Called by the wizard after the user confirms the spec and the backend creates the investigation
  const onInvestigationCreated = useCallback(async (invOut, spec) => {
    // Persist spec to localStorage so it survives page reloads (serverless is stateless).
    if (spec) _saveSavedSpec(invOut.id, { ...spec, id: invOut.id });
    // invOut is the InvestigationOut from POST /api/investigations
    const inv = invOut;
    const defaults = inv.defaults;

    // Register in local state
    setInvDetails(prev => ({ ...prev, [inv.id]: inv }));
    setValuesByCase(prev => ({ ...prev, [inv.id]: { ...defaults } }));

    // Compute initial result
    const result = await api.compute(inv.id, defaults);
    setComputedByCase(prev => ({ ...prev, [inv.id]: result }));

    // Add to sidebar list
    setInvestigations(prev => [
      ...prev,
      {
        id: inv.id,
        title: inv.title,
        subtitle: inv.subtitle,
        is_placeholder: false,
        top_label: result.top.label,
        top_p: result.top.p,
      },
    ]);

    // Navigate to new investigation
    setActiveId(inv.id);
    setOpenWhy(result.top.cause_id);
    setWizardOpen(false);
  }, []);

  const deleteInvestigation = useCallback((id) => {
    _removeSavedSpec(id);
    setInvestigations(prev => {
      const next = prev.filter(s => s.id !== id);
      if (activeId === id) {
        const fallback = next.find(s => !s.is_placeholder) || next[0];
        if (fallback) setActiveId(fallback.id);
      }
      return next;
    });
    setInvDetails(prev => { const n = { ...prev }; delete n[id]; return n; });
    setComputedByCase(prev => { const n = { ...prev }; delete n[id]; return n; });
    setValuesByCase(prev => { const n = { ...prev }; delete n[id]; return n; });
  }, [activeId]);

  const applyExtractedEvidence = useCallback(async (text) => {
    const inv = invDetails[activeId];
    if (!inv) return { ok: false, message: 'Investigation not loaded' };
    try {
      const out = await api.extractEvidence(activeId, text);
      setValuesByCase(prev => {
        const merged = { ...prev[activeId], ...out.evidence };
        computeRef.current?.(activeId, merged);
        return { ...prev, [activeId]: merged };
      });
      return { ok: true, llm_available: out.llm_available, message: out.message };
    } catch (e) {
      return { ok: false, message: e.message };
    }
  }, [activeId, invDetails]);

  const active = invDetails[activeId];
  const activeSummary = investigations.find(s => s.id === activeId);
  const computed = computedByCase[activeId] || null;
  const values = valuesByCase[activeId] || {};

  return {
    investigations,
    activeId,
    active,
    activeSummary,
    computed,
    values,
    openWhy,
    loading,
    error,
    wizardOpen,
    setValue,
    selectCase,
    setOpenWhy,
    openWizard,
    onInvestigationCreated,
    deleteInvestigation,
    applyExtractedEvidence,
  };
}
