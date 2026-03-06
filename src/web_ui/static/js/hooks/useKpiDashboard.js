import { useState, useCallback } from '../lib/ui.js';
import { toISODateInput } from '../utils/formatters.js';
import { fetchKpiOverview } from '../services/kpiService.js';

function firstDayOfMonth() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
}

export function useKpiDashboard() {
    const [startDate, setStartDate] = useState(toISODateInput(firstDayOfMonth()));
    const [endDate, setEndDate] = useState(toISODateInput(new Date()));
    const [rankingLimit, setRankingLimit] = useState(10);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [data, setData] = useState({
        filters: {},
        summary: {},
        ranking: [],
        novedades: { by_type: [], by_status: [] },
        trend: [],
        generated_at: ''
    });

    const fetchKpis = useCallback(() => {
        setLoading(true);
        setError('');
        fetchKpiOverview({ startDate, endDate, rankingLimit })
            .then((response) => {
                setData(response?.data || {
                    filters: {},
                    summary: {},
                    ranking: [],
                    novedades: { by_type: [], by_status: [] },
                    trend: [],
                    generated_at: ''
                });
            })
            .catch((err) => {
                setError(err?.message || 'No se pudo cargar el dashboard KPI.');
            })
            .finally(() => setLoading(false));
    }, [startDate, endDate, rankingLimit]);

    return {
        startDate,
        setStartDate,
        endDate,
        setEndDate,
        rankingLimit,
        setRankingLimit,
        loading,
        error,
        data,
        fetchKpis
    };
}