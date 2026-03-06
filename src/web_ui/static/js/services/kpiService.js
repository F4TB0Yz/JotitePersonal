import { get } from './http.js';

export function fetchKpiOverview({ startDate, endDate, rankingLimit = 10 } = {}) {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    params.set('ranking_limit', String(rankingLimit));
    return get(`/api/kpis/overview?${params.toString()}`);
}