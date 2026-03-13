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

export function getPhotoProxyDownloadUrl(photoUrl, filename) {
    const params = new URLSearchParams({ url: photoUrl, filename: filename || 'foto.jpeg' });
    return `/api/photos/proxy?${params.toString()}`;
}

export async function downloadPhoto(photoUrl, filename) {
    const url = getPhotoProxyDownloadUrl(photoUrl, filename);
    const response = await fetch(url, { credentials: 'same-origin' });

    if (!response.ok) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Error en el servidor al descargar foto');
        }
        throw new Error(`Error HTTP: ${response.status}`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
         throw new Error('El servidor devolvió JSON en lugar de una imagen. Verifique la URL.');
    }

    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    
    try {
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename || 'foto.jpeg';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    } finally {
        // Limpia el objeto URL para evitar fugas de memoria
        setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
    }
}

export async function downloadAllPhotos(waybillNo) {
    const url = getPhotosDownloadUrl(waybillNo);
    const response = await fetch(url, { credentials: 'same-origin' });

    if (!response.ok) {
        let detail = 'Error al descargar fotos';
        try {
            const errData = await response.json();
            detail = errData.detail || detail;
        } catch {}
        throw new Error(detail);
    }

    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const filename = `${waybillNo}_fotos_entrega.zip`;
    
    try {
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    } finally {
        setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
    }
}
