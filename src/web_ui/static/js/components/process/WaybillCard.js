import { html, useState } from '../../lib/ui.js';
import { fetchWaybillPhones } from '../../services/addressService.js';
import { fetchWaybillPhotos, getPhotosDownloadUrl } from '../../services/photosService.js';

export default function WaybillCard({ data, showArribo }) {
    const [phoneState, setPhoneState] = useState({
        loading: false,
        value: '',
        visible: false,
        error: ''
    });
    const [photosState, setPhotosState] = useState({
        open: false,
        loading: false,
        photos: [],
        error: ''
    });

    const isDelivered = data.is_delivered;
    const isError = data.status === 'Error';
    const cardFilterClass = isError ? 'card-error' : isDelivered ? 'card-delivered' : 'card-pending';
    const badge = isError ? 'ERROR' : isDelivered ? 'ENTREGADO' : 'SIN ENTREGAR';
    const statusClass = isError ? 'status-error' : isDelivered ? 'status-delivered' : 'status-pending';

    if (isError) {
        return html`
            <div className=${`waybill-card status-error ${cardFilterClass}`} data-date="">
                <div className="card-status-bar"></div>
                <div className="card-header">
                    <span className="wb-number">${data.waybill_no}</span>
                    <span className="wb-status-badge">${badge}</span>
                </div>
                <div className="card-body">
                    <p className="card-error-message">${data.exceptions || 'No se pudo obtener información'}</p>
                </div>
            </div>
        `;
    }

    const handlePhoneClick = () => {
        if (phoneState.loading) return;

        if (phoneState.value) {
            setPhoneState((prev) => ({ ...prev, visible: !prev.visible, error: '' }));
            return;
        }

        setPhoneState({ loading: true, value: '', visible: false, error: '' });
        fetchWaybillPhones([data.waybill_no])
            .then((response) => {
                const phone = response?.[data.waybill_no] || '';
                setPhoneState({
                    loading: false,
                    value: phone,
                    visible: Boolean(phone),
                    error: phone ? '' : 'Teléfono no disponible'
                });
            })
            .catch((err) => {
                setPhoneState({
                    loading: false,
                    value: '',
                    visible: false,
                    error: err.message || 'No se pudo consultar teléfono'
                });
            });
    };

    const arriboDate = data.arrival_punto6_time && data.arrival_punto6_time !== 'N/A' ? data.arrival_punto6_time.split(' ')[0] : '';

    const handlePhotosClick = () => {
        if (photosState.open) {
            setPhotosState({ open: false, loading: false, photos: [], error: '' });
            return;
        }
        if (photosState.photos.length > 0) {
            setPhotosState((prev) => ({ ...prev, open: true }));
            return;
        }
        setPhotosState({ open: true, loading: true, photos: [], error: '' });
        fetchWaybillPhotos(data.waybill_no)
            .then((payload) => {
                const photos = payload?.photos || [];
                const error = photos.length === 0 ? (payload?.error || 'Sin fotos disponibles') : '';
                setPhotosState({ open: true, loading: false, photos, error });
            })
            .catch((err) => {
                setPhotosState({ open: true, loading: false, photos: [], error: err.message || 'Error al cargar fotos' });
            });
    };

    return html`
        <div className=${`waybill-card ${statusClass} ${cardFilterClass}`}
             data-date=${arriboDate}>
            <div className="card-status-bar"></div>
            <div className="card-header">
                <span className="wb-number">${data.waybill_no}</span>
                <span className="wb-status-badge">${badge}</span>
            </div>
            <div className="card-body">
                <div className="info-row">
                    <span className="info-label">Destinatario</span>
                    <span className="info-value important">${data.receiver}</span>
                </div>
                <div className="info-row">
                    <span className="info-label">Dirección</span>
                    <span className="info-value">${data.address || 'N/A'}</span>
                </div>
                <div className="info-row">
                    <span className="info-label">Ciudad</span>
                    <span className="info-value">${data.city}</span>
                </div>
                <hr className="card-divider" />
                ${showArribo
                    ? html`<div className="info-row arribo-row">
                        <span className="info-label">Arribo P6</span>
                        <span className="info-value">${data.arrival_punto6_time || 'N/A'}</span>
                    </div>`
                    : null}
                ${isDelivered
                    ? html`<div className="info-row">
                        <span className="info-label">Entrega</span>
                        <span className="info-value success-text">${data.delivery_time}</span>
                    </div>`
                    : null}
            </div>
            <div className="card-footer-actions">
                <button
                    className="action-btn-phone no-print"
                    title="Ver teléfono del destinatario"
                    onClick=${handlePhoneClick}
                >
                    ${phoneState.loading
            ? 'Consultando teléfono…'
            : phoneState.visible
                ? '📞 Ocultar teléfono'
                : '📞 Ver teléfono'}
                </button>
                ${phoneState.visible && phoneState.value
            ? html`<p className="card-phone-value no-print">${phoneState.value}</p>`
            : null}
                ${phoneState.error
            ? html`<p className="card-phone-error no-print">${phoneState.error}</p>`
            : null}
                <button
                    className="action-btn-message no-print"
                    title="Generar mensaje para el cliente"
                    onClick=${() => window.dispatchEvent(new CustomEvent('open-message-templates', { detail: { waybill_no: data.waybill_no, receiver: data.receiver, city: data.city, address: data.address, delivery_time: (data.delivery_time && data.delivery_time !== 'N/A') ? data.delivery_time : (data.last_event_time || ''), sender: data.sender || '' } }))}
                >
                    💬 Mensaje
                </button>
                <button 
                    className="action-btn-novedad no-print" 
                    title="Añadir Novedad"
                    onClick=${() => window.dispatchEvent(new CustomEvent('open-novedades-modal', { detail: { waybill: data.waybill_no } }))}
                >
                    ⚠️ Reportar Novedad
                </button>
                ${isDelivered ? html`
                    <button
                        className="action-btn-photos no-print"
                        title="Ver fotos de entrega"
                        onClick=${handlePhotosClick}
                    >
                        📸 ${photosState.open ? 'Ocultar fotos' : 'Ver fotos'}
                    </button>
                    ${photosState.open ? html`
                        <div className="card-photos-panel no-print">
                            ${photosState.loading ? html`<p className="photos-state">Cargando fotos...</p>` : null}
                            ${photosState.error && !photosState.loading ? html`<p className="photos-state error">${photosState.error}</p>` : null}
                            ${!photosState.loading && photosState.photos.length > 0 ? html`
                                <div className="photos-grid">
                                    ${photosState.photos.map((url, i) => html`
                                        <a key=${i} href=${url} target="_blank" rel="noopener noreferrer" className="photo-thumb-link">
                                            <img src=${url} alt=${'Foto ' + (i + 1)} className="photo-thumb" loading="lazy" />
                                        </a>
                                    `)}
                                </div>
                                <a
                                    href=${getPhotosDownloadUrl(data.waybill_no)}
                                    download
                                    className="photos-download-link no-print"
                                >⬇ Descargar todas</a>
                            ` : null}
                        </div>
                    ` : null}
                ` : null}
            </div>
        </div>
    `;
}
