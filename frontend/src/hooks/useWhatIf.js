import { useState, useEffect, useCallback, useRef } from 'react';
import { api, debounce } from '../api.js';

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
        const summaries = await api.listInvestigations();
        setInvestigations(summaries);
        setActiveId(summaries[0]?.id || 'electricity');

        const details = await Promise.all(
          summaries.filter(s => !s.is_placeholder).map(s => api.getInvestigation(s.id))
        );

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
  const onInvestigationCreated = useCallback(async (invOut) => {
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
    applyExtractedEvidence,
  };
}
