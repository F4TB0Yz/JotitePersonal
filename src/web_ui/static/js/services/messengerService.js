import { get, post } from './http.js';

export function searchMessengers(query) {
    if (!query || query.trim().length < 2) return Promise.resolve([]);
    return get(`/api/messengers/search?q=${encodeURIComponent(query.trim())}`);
}

export function fetchMessengerMetrics(accountCode, networkCode, start, end) {
    if (!accountCode || !start || !end) {
        return Promise.resolve({ summary: [], detail: [] });
    }
    const params = new URLSearchParams({
        account_code: accountCode,
        network_code: networkCode || '',
        start_time: start,
        end_time: end
    });
    return get(`/api/messengers/metrics?${params.toString()}`);
}

export function fetchMessengerWaybills(accountCode, networkCode, start, end) {
    if (!accountCode || !start || !end) return Promise.resolve([]);
    const params = new URLSearchParams({
        account_code: accountCode,
        network_code: networkCode || '',
        start_time: start,
        end_time: end
    });
    return get(`/api/messengers/waybills?${params.toString()}`);
}

export function fetchMessengerContact(name, networkCode, waybillNo) {
    if (!name) return Promise.resolve(null);
    const params = new URLSearchParams({ name: name.trim() });
    if (networkCode) {
        params.append('network_code', networkCode.trim());
    }
    if (waybillNo) {
        params.append('waybill', waybillNo.trim());
    }
    return get(`/api/messengers/contact?${params.toString()}`);
}

export function fetchBulkMetrics(messengers, startTime, endTime) {
    if (!messengers?.length || !startTime || !endTime) {
        return Promise.resolve({ results: [] });
    }
    return post('/api/messengers/bulk-metrics', { messengers, startTime, endTime });
}
