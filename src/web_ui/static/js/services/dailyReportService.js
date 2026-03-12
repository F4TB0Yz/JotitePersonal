import { get, post, httpDelete, patch } from './http.js';

export function fetchDailyReportEntries(startDate, endDate) {
    return get(`/api/daily-report/entries?start_date=${startDate}&end_date=${endDate}`);
}

export function ingestDailyReportEntries(waybillNos, reportDate) {
    return post('/api/daily-report/entries', { waybill_nos: waybillNos, report_date: reportDate });
}

export function deleteDailyReportEntry(id) {
    return httpDelete(`/api/daily-report/entries/${id}`);
}

export function updateDailyReportEntry(id, updates) {
    return patch(`/api/daily-report/entries/${id}`, updates);
}
