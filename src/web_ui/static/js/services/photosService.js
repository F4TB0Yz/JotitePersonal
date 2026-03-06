import { get } from './http.js';

export function fetchWaybillPhotos(waybillNo) {
    const waybill = (waybillNo || '').trim().toUpperCase();
    if (!waybill) return Promise.resolve({ waybill_no: '', photos: [] });
    return get(`/api/waybills/${encodeURIComponent(waybill)}/photos`);
}

export function getPhotosDownloadUrl(waybillNo) {
    const waybill = (waybillNo || '').trim().toUpperCase();
    return `/api/waybills/${encodeURIComponent(waybill)}/photos/download`;
}
