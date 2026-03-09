import { post } from './http.js';

export function fetchAddressesForWaybills(waybills) {
    if (!Array.isArray(waybills) || waybills.length === 0) return Promise.resolve({});
    return post('/api/waybills/addresses', { waybills });
}

export function fetchWaybillDetails(waybills) {
    if (!Array.isArray(waybills) || waybills.length === 0) return Promise.resolve({});
    return post('/api/waybills/details', { waybills });
}

export function fetchWaybillIntelligenceExport(waybills) {
    if (!Array.isArray(waybills) || waybills.length === 0) {
        return Promise.resolve({ generatedAt: '', results: {} });
    }
    return post('/api/waybills/intelligence-export', { waybills });
}

export function fetchWaybillPhones(waybills) {
    if (!Array.isArray(waybills) || waybills.length === 0) return Promise.resolve({});
    return post('/api/waybills/phones', { waybills });
}
