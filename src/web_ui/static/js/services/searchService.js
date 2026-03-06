import { get } from './http.js';

export function globalSearch(query, limit = 6) {
    const q = (query || '').trim();
    if (q.length < 2) {
        return Promise.resolve({ waybills: [], messengers: [], novedades: [] });
    }
    const params = new URLSearchParams({ q, limit: String(limit) });
    return get(`/api/search?${params.toString()}`);
}
