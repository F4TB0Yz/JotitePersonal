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

export function fetchCellDetails(networkCode, start, end, staff, date, dateMode) {
    return post('/api/network/waybills', {
        networkCode,
        startTime: start,
        endTime: end,
        signType: 0,
        target_staff: staff,
        target_date: date === 'ALL' ? null : date
    });
}
