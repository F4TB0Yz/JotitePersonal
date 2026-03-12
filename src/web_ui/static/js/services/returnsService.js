import { get, post } from './http.js';

export function fetchReturnApplications({
    status = 1,
    dateFrom,
    dateTo,
    current = 1,
    size = 20,
    saveSnapshot = true,
} = {}) {
    const params = new URLSearchParams();
    params.set('status', String(status));
    params.set('current', String(current));
    params.set('size', String(size));
    params.set('save_snapshot', String(Boolean(saveSnapshot)));
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    return get(`/api/returns/applications?${params.toString()}`);
}

export function fetchReturnSnapshots({
    status,
    waybillNo,
    dateFrom,
    dateTo,
    limit = 100,
    offset = 0,
} = {}) {
    const params = new URLSearchParams();
    if (status === 1 || status === 2) params.set('status', String(status));
    if (waybillNo) params.set('waybill_no', waybillNo);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    return get(`/api/returns/snapshots?${params.toString()}`);
}

export function syncReturnSnapshots(payload = {}) {
    return post('/api/returns/sync', payload);
}
