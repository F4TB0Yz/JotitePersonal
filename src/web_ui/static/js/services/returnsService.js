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
    if (status === 1 || status === 2 || status === 3) params.set('status', String(status));
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

export function fetchReturnPrintable({
    dateFrom,
    dateTo,
    current = 1,
    size = 20,
    pringFlag = 0,
    printer = 0,
    templateSize = 1,
    pringType = 1,
} = {}) {
    const params = new URLSearchParams();
    params.set('current', String(current));
    params.set('size', String(size));
    params.set('pring_flag', String(pringFlag));
    params.set('printer', String(printer));
    params.set('template_size', String(templateSize));
    params.set('pring_type', String(pringType));
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    return get(`/api/returns/printable?${params.toString()}`);
}

export function fetchReturnPrintUrl({
    waybillNo,
    templateSize = 1,
    pringType = 1,
    printer = 0,
    printFlag = 0,
    printCount = 0,
} = {}) {
    const resolvedPrinter = Number(printer || 0) || (Number(printFlag || 0) === 1 || Number(printCount || 0) > 0 ? 1 : 0);

    return post('/api/returns/print-url', {
        waybill_no: waybillNo,
        template_size: Number(templateSize || 1),
        pring_type: Number(pringType || 1),
        printer: resolvedPrinter,
    });
}
