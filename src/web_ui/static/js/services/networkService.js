import { post, get } from './http.js';

export function fetchPendingWaybills(networkCode, start, end, dateMode) {
    return post('/api/network/waybills', {
        networkCode,
        startTime: start,
        endTime: end,
        signType: 0,
        dateMode
    });
}

export function fetchCellDetails(networkCode, staff, date, dateMode) {
    return get(`/api/network/waybills?networkCode=${encodeURIComponent(networkCode)}&staff=${encodeURIComponent(staff)}&date=${encodeURIComponent(date)}&dateMode=${encodeURIComponent(dateMode || '')}`);
}
