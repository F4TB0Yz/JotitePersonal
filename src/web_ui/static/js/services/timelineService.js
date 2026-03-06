import { get } from './http.js';

export function fetchWaybillTimeline(waybillNo, maxAgeMinutes = 30) {
    const waybill = (waybillNo || '').trim().toUpperCase();
    if (!waybill) return Promise.resolve({ waybill_no: '', current_status: 'Desconocido', events: [] });
    const params = new URLSearchParams({ max_age_minutes: String(maxAgeMinutes) });
    return get(`/api/waybills/${encodeURIComponent(waybill)}/timeline?${params.toString()}`);
}
