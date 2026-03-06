import { html } from '../../lib/ui.js';
import { STATUS_DICTIONARY } from '../../utils/constants.js';

function translateStatus(status) {
    if (!status) return 'Sin estado';
    return STATUS_DICTIONARY[status] || status;
}

function resolveStatusClass(status) {
    const normalized = (status || '').toLowerCase();
    if (normalized.includes('firmado') || normalized.includes('entregado')) return 'delivered';
    if (normalized.includes('incidencia') || normalized.includes('rechazado') || normalized.includes('devuelto')) return 'issue';
    return 'in-transit';
}

export default function WaybillTimeline({ events = [], loading = false, error = '' }) {
    if (loading) {
        return html`<div className="timeline-state">Cargando timeline...</div>`;
    }

    if (error) {
        return html`<div className="timeline-state error">${error}</div>`;
    }

    if (!events || events.length === 0) {
        return html`<div className="timeline-state">Sin eventos disponibles para esta guía.</div>`;
    }

    return html`
        <section className="timeline-wrapper">
            <h4 className="timeline-title">Timeline de Estado</h4>
            <div className="timeline-list">
                ${events.map((event, index) => {
                    const statusText = translateStatus(event.status);
                    const statusClass = resolveStatusClass(statusText);
                    return html`
                        <article key=${`${event.time}-${event.type_name}-${index}`} className="timeline-item">
                            <div className=${`timeline-dot ${statusClass}`}></div>
                            <div className="timeline-card">
                                <div className="timeline-head">
                                    <strong>${statusText}</strong>
                                    <span>${event.time || 'N/A'}</span>
                                </div>
                                <div className="timeline-meta">
                                    <span>${event.type_name || 'Evento'}</span>
                                    <span>${event.network_name || 'Red desconocida'}</span>
                                </div>
                                <p className="timeline-content">${event.content || 'Sin detalle adicional'}</p>
                                ${event.staff_name || event.staff_contact
                                    ? html`<small className="timeline-staff">
                                        ${event.staff_name || 'Sin asignar'}
                                        ${event.staff_contact ? ` · ${event.staff_contact}` : ''}
                                    </small>`
                                    : null}
                            </div>
                        </article>
                    `;
                })}
            </div>
        </section>
    `;
}
