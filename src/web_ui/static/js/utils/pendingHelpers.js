export function cellClass(value) {
    if (!value) return 'dash-cell-empty';
    if (value <= 5) return 'dash-cell-verylow';
    if (value <= 15) return 'dash-cell-low';
    if (value <= 30) return 'dash-cell-med';
    return 'dash-cell-high';
}

export function resolveValue(options, fallback = '—') {
    for (const value of options) {
        if (value && value !== 'N/A') return value;
    }
    return fallback;
}

export function getWaybillId(record, index) {
    return record.waybillNo || record.thirdWaybillNo || record.orderId || `registro-${index}`;
}

export function getReceiverName(record) {
    return resolveValue([record.receiverName, record.receiver, record.receiverRealName, record.customerName], 'Sin destinatario');
}

export function getReceiverCity(record) {
    return resolveValue([record.receiverCityName, record.receiverCity, record.receiverCitye, record.destCityName], 'Ciudad desconocida');
}

export function getReceiverAddress(record) {
    return resolveValue([record.receiverAddress, record.receiverAddressDetail, record.receAddress, record.destAddress], 'Sin dirección registrada');
}

export function getPackageStatus(record) {
    return resolveValue([record.statusName, record.status, record.waybillStatusName], 'Pendiente');
}

export function pickFirstDate(record, fields, fallback = 'Sin Fecha') {
    for (const field of fields) {
        const value = record?.[field];
        if (value && value !== 'N/A') return value;
    }
    return fallback;
}

export function getPackageDateByMode(record, dateMode, dateModes) {
    if (dateMode === dateModes.assignment) {
        return pickFirstDate(record, [
            'deliveryScanTimeLatest',
            'dispatchTime',
            'assignTime',
            'deliveryTime',
            'operateTime',
            'destArrivalTime',
            'dateTime',
            'deadLineTime',
            'createTime',
            'updateTime',
            'scanTime'
        ]);
    }
    return pickFirstDate(record, [
        'destArrivalTime',
        'arrivalTime',
        'arriveTime',
        'inboundTime',
        'dispatchTime',
        'operateTime',
        'updateTime'
    ]);
}

export function getSortTimestamp(value) {
    if (!value || value === 'Sin Fecha') return 0;
    const ts = new Date(value).getTime();
    return Number.isNaN(ts) ? 0 : ts;
}

export function getPhoneButtonLabel(info) {
    if (!info) return '📞 Ver teléfono';
    if (info.loading) return 'Consultando…';
    if (info.value && info.visible) return 'Ocultar';
    return '📞 Ver teléfono';
}

export function safeFileNamePart(value, fallback = 'sin-valor') {
    const normalized = String(value || '')
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-zA-Z0-9_-]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .toLowerCase();
    return normalized || fallback;
}

export function downloadJsonFile(fileName, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}

export const EXPORTABLE_FIELDS = [
    { key: 'waybillNo', label: 'Guía' },
    { key: 'receiverName', label: 'Destinatario' },
    { key: 'receiverCity', label: 'Ciudad' },
    { key: 'receiverAddress', label: 'Dirección' },
    { key: 'receiverPhone', label: 'Contacto' },
    { key: 'date', label: 'Fecha' },
    { key: 'status', label: 'Estado' },
    { key: 'staff', label: 'Mensajero' }
];
