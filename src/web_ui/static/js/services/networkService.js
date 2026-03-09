import { post } from './http.js';

export function fetchPendingWaybills(networkCode, start, end) {
    return post('/api/network/waybills', {
        networkCode,
        startTime: start,
        endTime: end,
        signType: 0
    });
}
