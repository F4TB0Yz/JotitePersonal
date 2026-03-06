import { html, useState, useEffect, useCallback, useMemo, useRef } from '../../lib/ui.js';
import { fetchTemuAlerts } from '../../services/alertService.js';
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

function AlertEntry({ alert, thresholdBase, onShowBarcode }) {
    const excess = Math.max((alert.hoursSinceEvent || 0) - thresholdBase, 0);
    return html`
        <article className=${`temu-alert-entry severity-${alert.status}`}>
            <header className="temu-alert-entry-header">
                <div>
                    <p className="temu-alert-entry-label">Guía</p>
                    <h4>${alert.billcode || 'Sin guía'}</h4>
                </div>
                <AlertStatusBadge status=${alert.status} />
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

function BarcodeSlide({ value, goods, weight, staff, operateTime }) {
    const svgRef = useRef(null);
    useEffect(() => {
        if (window.JsBarcode && svgRef.current && value) {
            try {
                window.JsBarcode(svgRef.current, value, {
                    format: 'code128',
                    lineColor: '#111111',
                    background: '#ffffff',
                    displayValue: false,
                    margin: 0,
                    height: 140,
                    width: 2
                });
            } catch (err) {
                console.error('Barcode render error', err);
            }
        }
    }, [value]);

    return html`
        <div className="barcode-slide">
            <div className="barcode-metadata">
                <p>${goods || 'Contenido no disponible'}</p>
                <p>${weight ? `${weight} kg` : ''}</p>
            </div>
            <svg ref=${svgRef} className="barcode-svg" role="img" aria-label=${`Código ${value}`}></svg>
            <p className="barcode-value">${value}</p>
            <div className="barcode-meta-foot">
                <span>${staff || 'Sin operador'}</span>
                <span>${formatDateTimeLabel(operateTime)}</span>
            </div>
        </div>
    `;
}

function BarcodeModal({ items, index, onClose, onPrev, onNext }) {
    const current = items[index];
    return html`
        <div className="barcode-overlay" onClick=${onClose}>
            <div className="barcode-window" onClick=${(event) => event.stopPropagation()}>
                <header>
                    <div>
                        <p>Modo escáner</p>
                        <h4>${current?.value || 'Sin datos'}</h4>
                    </div>
                    <button type="button" className="barcode-close" onClick=${onClose}>Cerrar ✕</button>
                </header>
                <div className="barcode-carousel">
                    ${current
                        ? html`<${BarcodeSlide}
                            value=${current.value}
                            goods=${current.goods}
                            weight=${current.weight}
                            staff=${current.staff}
                            operateTime=${current.operateTime}
                        />`
                        : html`<p className="barcode-empty">Sin guías para mostrar.</p>`}
                </div>
                <footer>
                    <button type="button" className="barcode-nav" onClick=${onPrev} disabled=${items.length <= 1}>
                        ◀
                    </button>
                    <span>${items.length ? `${index + 1} / ${items.length}` : '0 / 0'}</span>
                    <button type="button" className="barcode-nav" onClick=${onNext} disabled=${items.length <= 1}>
                        ▶
                    </button>
                </footer>
            </div>
        </div>
    `;
}

export default function TemuAlertCenter({ isActive }) {
    const [windowHours, setWindowHours] = useState(12);
    const [includeOverdue, setIncludeOverdue] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [data, setData] = useState({ alerts: [], summary: {}, generatedAt: '' });
    const [barcodeModal, setBarcodeModal] = useState({ open: false, items: [], index: 0 });
    const [realtimeNote, setRealtimeNote] = useState('');

    const alerts = data.alerts || [];
    const { warningCount = 0, breachedCount = 0, totalCandidates = 0 } = data;
    const summary = data.summary || {};
    const generatedAt = data.generatedAt ? formatDateTimeLabel(data.generatedAt) : 'Sin actualizar';
    const thresholdBase = data.thresholdHours || 96;

    const grouped = useMemo(() => ({
        breached: alerts.filter((item) => item.status === 'breached'),
        warning: alerts.filter((item) => item.status === 'warning')
    }), [alerts]);

    const barcodeItems = useMemo(() =>
        grouped.breached.map((alert) => ({
            value: alert.billcode,
            goods: alert.goodsName,
            weight: alert.weight,
            staff: alert.staff,
            operateTime: alert.operateTime
        })),
        [grouped.breached]
    );

    const openBarcodeViewer = useCallback((startIndex = 0) => {
        if (!barcodeItems.length) return;
        const safeIndex = Math.min(Math.max(startIndex, 0), barcodeItems.length - 1);
        setBarcodeModal({ open: true, items: barcodeItems, index: safeIndex });
    }, [barcodeItems]);

    const closeBarcodeViewer = useCallback(() => {
        setBarcodeModal((prev) => ({ ...prev, open: false }));
    }, []);

    const shiftBarcode = useCallback((delta) => {
        setBarcodeModal((prev) => {
            if (!prev.items.length) return prev;
            const nextIndex = (prev.index + delta + prev.items.length) % prev.items.length;
            return { ...prev, index: nextIndex };
        });
    }, []);

    useEffect(() => {
        if (!barcodeModal.open) return undefined;
        const handleKey = (event) => {
            if (event.key === 'Escape') {
                event.preventDefault();
                closeBarcodeViewer();
            } else if (event.key === 'ArrowRight') {
                shiftBarcode(1);
            } else if (event.key === 'ArrowLeft') {
                shiftBarcode(-1);
            }
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [barcodeModal.open, closeBarcodeViewer, shiftBarcode]);

    useEffect(() => {
        if (!barcodeModal.open) return;
        setBarcodeModal((prev) => {
            if (!barcodeItems.length) {
                return { open: false, items: [], index: 0 };
            }
            const safeIndex = Math.min(prev.index, barcodeItems.length - 1);
            return { ...prev, items: barcodeItems, index: safeIndex };
        });
    }, [barcodeItems, barcodeModal.open]);

    const loadData = useCallback(() => {
        setLoading(true);
        setError('');
        fetchTemuAlerts({ windowHours, includeOverdue })
            .then((response) => setData(response))
            .catch((err) => setError(err?.message || 'No se pudo cargar el monitoreo.'))
            .finally(() => setLoading(false));
    }, [windowHours, includeOverdue]);

    useEffect(() => {
        if (!isActive) return undefined;
        loadData();
        const interval = setInterval(loadData, 60 * 60 * 1000);
        return () => clearInterval(interval);
    }, [isActive, loadData]);

    useEffect(() => {
        const onPredictedBreach = (event) => {
            const payload = event?.detail;
            if (!payload?.billcode) return;

            setData((prev) => {
                const previousAlerts = prev.alerts || [];
                const alreadyExists = previousAlerts.some((item) => item.billcode === payload.billcode);
                if (alreadyExists) {
                    return prev;
                }

                const nextAlert = {
                    ...payload,
                    status: 'breached',
                    hoursToThreshold: 0,
                    hoursSinceEvent: Number(payload.hoursSinceEvent || 96),
                };

                return {
                    ...prev,
                    generatedAt: new Date().toISOString(),
                    alerts: [nextAlert, ...previousAlerts],
                    breachedCount: (prev.breachedCount || 0) + 1,
                };
            });

            setRealtimeNote(`Nueva crítica detectada: ${payload.billcode}`);
            setTimeout(() => setRealtimeNote(''), 7000);
        };

        window.addEventListener('temu-breach-predicted', onPredictedBreach);
        return () => window.removeEventListener('temu-breach-predicted', onPredictedBreach);
    }, []);

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
                    action: grouped.breached.length
                        ? html`<button type="button" className="temu-alert-barcode-btn" onClick=${() => openBarcodeViewer(0)}>
                            Modo escáner (${grouped.breached.length})
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
                />`
                : null}
        </main>
    `;
}
