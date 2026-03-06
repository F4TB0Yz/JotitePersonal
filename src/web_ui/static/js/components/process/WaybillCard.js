import { html } from '../../lib/ui.js';

export default function WaybillCard({ data, showArribo }) {
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

    const arriboDate = data.arrival_punto6_time && data.arrival_punto6_time !== 'N/A' ? data.arrival_punto6_time.split(' ')[0] : '';

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
                    className="action-btn-novedad no-print" 
                    title="Añadir Novedad"
                    onClick=${() => window.dispatchEvent(new CustomEvent('open-novedades-modal', { detail: { waybill: data.waybill_no } }))}
                >
                    ⚠️ Reportar Novedad
                </button>
            </div>
        </div>
    `;
}
