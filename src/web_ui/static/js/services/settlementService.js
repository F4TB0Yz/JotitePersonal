import { get, post } from './http.js';

export function setMessengerRate(accountCode, accountName, ratePerDelivery) {
    return post('/api/settlements/rate', {
        account_code: accountCode,
        account_name: accountName,
        rate_per_delivery: Number(ratePerDelivery || 0)
    });
}

export function fetchMessengerRate(accountCode) {
    const params = new URLSearchParams({ account_code: accountCode || '' });
    return get(`/api/settlements/rate?${params.toString()}`);
}

export function generateSettlement(payload) {
    return post('/api/settlements/generate', payload);
}

export function reprintWaybills(waybillIds, billType = 'small') {
    return post('/api/waybills/reprint', {
        waybill_ids: waybillIds,
        bill_type: billType
    });
}

export function fetchSettlements(accountCode, limit = 10) {
    const params = new URLSearchParams();
    if (accountCode) params.set('account_code', accountCode);
    params.set('limit', String(limit));
    return get(`/api/settlements?${params.toString()}`);
}

export async function deleteSettlement(settlementId) {
    const response = await fetch(`/api/settlements/${settlementId}`, {
        method: 'DELETE',
        headers: { Accept: 'application/json' }
    });
    if (!response.ok) {
        let detail = 'No se pudo eliminar la liquidación.';
        try {
            const data = await response.json();
            detail = data.detail || detail;
        } catch (_err) {
            // ignore
        }
        throw new Error(detail);
    }
    return response.json();
}
