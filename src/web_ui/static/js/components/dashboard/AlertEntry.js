import { html } from '../../lib/ui.js';
import { formatHours, formatDateTimeLabel } from '../../utils/formatters.js';

function AlertStatusBadge({ status }) {
    const label = status === 'breached' ? '⚠️ Vencida' : '⏳ Próxima';
    return html`<span className=${`temu-alert-badge temu-alert-${status}`}>${label}</span>`;
}

function AlertChips({ customer, duty }) {
    return html`
        <div className="temu-alert-chips">
            ${customer ? html`<span className="temu-alert-chip">${customer}</span>` : null}
            ${duty ? html`<span className="temu-alert-chip outline">${duty}</span>` : null}
        </div>
    `;
}

export default function AlertEntry({ alert, thresholdBase, onShowBarcode }) {
    const excess = Math.max((alert.hoursSinceEvent || 0) - thresholdBase, 0);
    return html`
        <article className=${`temu-alert-entry severity-${alert.status}`}>
            <header className="temu-alert-entry-header">
                <div>
                    <p className="temu-alert-entry-label">Guía</p>
                    <h4>${alert.billcode || 'Sin guía'}</h4>
                </div>
                <${AlertStatusBadge} status=${alert.status} />
            </header>
            ${html`<${AlertChips}
                customer=${alert.customerName || 'Cliente desconocido'}
                duty=${alert.dutyName || alert.managerDesc || 'Sin punto asignado'}
            />`}
            <dl className="temu-alert-entry-grid">
                <div>
                    <dt>Última operación</dt>
                    <dd>
                        <strong>${alert.operateType || '—'}</strong>
                        <small>${alert.problemOperateType || 'Sin detalle'}</small>
                    </dd>
                </div>
                <div>
                    <dt>Registro</dt>
                    <dd>
                        <span>${formatDateTimeLabel(alert.operateTime)}</span>
                        <small>${alert.operateAgentName || alert.operateNetworkName || 'Sin red'}</small>
                    </dd>
                </div>
                <div>
                    <dt>Horas</dt>
                    <dd>
                        <span>${formatHours(alert.hoursSinceEvent)}</span>
                        <small>
                            ${alert.status === 'breached'
                                ? `Exceso ${formatHours(excess)}`
                                : `Restan ${formatHours(alert.hoursToThreshold)}`}
                        </small>
                    </dd>
                </div>
                <div>
                    <dt>Responsable</dt>
                    <dd>
                        <span>${alert.staff || 'Sin operador'}</span>
                        <small>${alert.managerDesc || '—'}</small>
                    </dd>
                </div>
                <div>
                    <dt>Peso</dt>
                    <dd>
                        <span>${alert.weight ? `${alert.weight} kg` : '—'}</span>
                        <small>${alert.goodsName || 'Sin detalle de contenido'}</small>
                    </dd>
                </div>
            </dl>
            ${onShowBarcode
                ? html`<button type="button" className="temu-alert-barcode-btn" onClick=${onShowBarcode}>
                    Ver código de barras
                </button>`
                : null}
        </article>
    `;
}
