import { html, useState, useEffect, useCallback, useMemo, useRef } from '../../lib/ui.js';
import useTemuAlerts from '../../hooks/useTemuAlerts.js';
import useBarcodeCarousel from '../../hooks/useBarcodeCarousel.js';
import AlertEntry from './AlertEntry.js';
import BarcodeModal from './BarcodeViewer.js';
import { formatHours, formatDateTimeLabel } from '../../utils/formatters.js';
import { fetchTemuAlerts } from '../../services/alertService.js';

export default function TemuAlertCenter({ isActive }) {
    const { 
        windowHours, setWindowHours, includeOverdue, setIncludeOverdue, 
        loading, error, data, realtimeNote, loadData 
    } = useTemuAlerts({ isActive });

    const [festivoMode, setFestivoMode] = useState(false);
    const [festivoItems, setFestivoItems] = useState([]);
    const [festivoLoading, setFestivoLoading] = useState(false);

    const alerts = data.alerts || [];
    const { warningCount = 0, breachedCount = 0, totalCandidates = 0 } = data;
    const summary = data.summary || {};
    const generatedAt = data.generatedAt ? formatDateTimeLabel(data.generatedAt) : 'Sin actualizar';
    const thresholdBase = data.thresholdHours || 96;

    const grouped = useMemo(() => ({
        breached: alerts.filter((item) => item.status === 'breached'),
        warning: alerts.filter((item) => item.status === 'warning')
    }), [alerts]);

    // Cuando se activa el modo festivo, carga TODOS los paquetes ≥72h desde el API
    const loadFestivoData = useCallback(() => {
        setFestivoLoading(true);
        fetchTemuAlerts({ thresholdHours: 72, windowHours: 9999, includeOverdue: true })
            .then((response) => {
                const all72 = (response.alerts || []).map((alert) => ({
                    value: alert.billcode,
                    goods: alert.goodsName,
                    weight: alert.weight,
                    staff: alert.staff,
                    operateTime: alert.operateTime
                }));
                setFestivoItems(all72);
            })
            .catch(() => setFestivoItems([]))
            .finally(() => setFestivoLoading(false));
    }, []);

    useEffect(() => {
        if (festivoMode) {
            loadFestivoData();
        } else {
            setFestivoItems([]);
        }
    }, [festivoMode, loadFestivoData]);

    const barcodeItems = festivoMode ? festivoItems : grouped.breached.map((alert) => ({
        value: alert.billcode,
        goods: alert.goodsName,
        weight: alert.weight,
        staff: alert.staff,
        operateTime: alert.operateTime
    }));

    const { barcodeModal, openBarcodeViewer, closeBarcodeViewer, shiftBarcode } = useBarcodeCarousel(barcodeItems);

    const renderPanel = (items, panel, options = {}) => {
        const indexed = items.map((alert, idx) => ({ alert, idx }));
        return html`
            <section className=${`temu-alert-panel ${panel.variant}`}>
                <header>
                    <div>
                        <p className="temu-alert-panel-kicker">${panel.kicker}</p>
                        <h3>${panel.title}</h3>
                        <p>${panel.description}</p>
                    </div>
                    <span className="temu-alert-panel-count">${items.length}</span>
                    ${options.action ? html`<div className="temu-alert-panel-actions">${options.action}</div>` : null}
                </header>
                <div className="temu-alert-panel-body">
                    ${indexed.length === 0
                        ? html`<div className="temu-alert-empty">${loading ? 'Cargando…' : 'Sin guías en este bloque.'}</div>`
                        : indexed.map(({ alert, idx }) => html`<${AlertEntry}
                            alert=${alert}
                            thresholdBase=${thresholdBase}
                            key=${`${panel.variant}-${alert.billcode}`}
                            onShowBarcode=${options.enableBarcode ? () => openBarcodeViewer(idx) : undefined}
                        />`)}
                </div>
            </section>
        `;
    };

    return html`
        <main className="temu-alert-main">
            <div className="temu-alert-hero">
                <div>
                    <p className="temu-alert-kicker">Monitoreo TEMU</p>
                    <h2>Alertas cercanas al límite de 96 horas</h2>
                    <p>Controla los paquetes en riesgo antes de que excedan el tiempo máximo sin actualización.</p>
                </div>
                <div className="temu-alert-controls">
                    <label>
                        Ventana de alerta (horas)
                        <input
                            type="number"
                            min="1"
                            max="48"
                            value=${windowHours}
                            onChange=${(event) => {
                                const parsed = parseInt(event.target.value, 10);
                                const next = Number.isNaN(parsed) ? 1 : Math.min(Math.max(parsed, 1), 48);
                                setWindowHours(next);
                            }}
                        />
                    </label>
                    <label className="temu-alert-toggle">
                        <input
                            type="checkbox"
                            checked=${includeOverdue}
                            onChange=${(event) => setIncludeOverdue(event.target.checked)}
                        />
                        <span>Incluir guías ya vencidas</span>
                    </label>
                    <button
                        type="button"
                        className=${`temu-alert-festivo-btn${festivoMode ? ' active' : ''}`}
                        onClick=${() => setFestivoMode((prev) => !prev)}
                        disabled=${festivoLoading}
                    >
                        ${festivoLoading ? 'Cargando 72h…' : festivoMode ? '🎉 Desactivar Modo Festivo' : '🎉 Modo Festivo'}
                    </button>
                    <button type="button" className="primary-btn" onClick=${loadData} disabled=${loading}>
                        ${loading ? 'Actualizando…' : 'Actualizar ahora'}
                    </button>
                    <span className="temu-alert-updated">Última actualización: ${generatedAt}</span>
                </div>
            </div>

            <div className="temu-alert-cards">
                <div className="temu-alert-card">
                    <p className="card-label">Próximas a 96h</p>
                    <p className="card-value">${warningCount}</p>
                </div>
                <div className="temu-alert-card danger">
                    <p className="card-label">Superaron 96h</p>
                    <p className="card-value">${includeOverdue ? breachedCount : '—'}</p>
                </div>
                <div className="temu-alert-card muted">
                    <p className="card-label">Total monitoreadas</p>
                    <p className="card-value">${totalCandidates}</p>
                </div>
                <div className="temu-alert-card outline">
                    <p className="card-label">Horas >72h</p>
                    <p className="card-value">${summary?.hoursOver72 ?? '0'}</p>
                </div>
                <div className="temu-alert-card outline">
                    <p className="card-label">Horas >96h</p>
                    <p className="card-value">${summary?.hoursOver96 ?? '0'}</p>
                </div>
            </div>

            ${error ? html`<div className="temu-alert-error">${error}</div>` : null}
            ${realtimeNote ? html`<div className="temu-alert-error">${realtimeNote}</div>` : null}

            <div className="temu-alert-panels">
                ${renderPanel(grouped.breached, {
                    title: 'Críticas (≥96h)',
                    description: 'Intervención inmediata. Ordenadas por mayor exceso sobre el límite.',
                    kicker: 'Prioridad 1',
                    variant: 'critical'
                }, {
                    enableBarcode: true,
                    action: barcodeItems.length
                        ? html`<button type="button" className="temu-alert-barcode-btn" onClick=${() => openBarcodeViewer(0)}>
                            Modo escáner (${barcodeItems.length})
                        </button>`
                        : null
                })}
                ${renderPanel(grouped.warning, {
                    title: 'En riesgo (<96h)',
                    description: `Ventana de ${windowHours}h para actuar antes de que venzan.`,
                    kicker: 'Prioridad 2',
                    variant: 'warning'
                })}
            </div>

            ${barcodeModal.open
                ? html`<${BarcodeModal}
                    items=${barcodeModal.items}
                    index=${barcodeModal.index}
                    onClose=${closeBarcodeViewer}
                    onPrev=${() => shiftBarcode(-1)}
                    onNext=${() => shiftBarcode(1)}
                    festivo=${festivoMode}
                />`
                : null}
        </main>
    `;
}
