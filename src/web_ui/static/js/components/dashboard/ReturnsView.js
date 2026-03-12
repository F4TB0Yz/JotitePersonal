import { html, useEffect } from '../../lib/ui.js';
import DateRangePicker from '../shared/DateRangePicker.js';
import { useReturns } from '../../hooks/useReturns.js';
import { formatDateTimeLabel } from '../../utils/formatters.js';

function statusLabel(value) {
    if (value === 'printable') return 'Para imprimir';
    const safe = Number(value);
    if (safe === 2) return 'Aprobadas';
    if (safe === 3) return 'Rechazadas';
    return 'En revisión';
}

function printFlagLabel(value) {
    return Number(value) === 1 ? 'Sí' : 'No';
}

export default function ReturnsView({ isActive }) {
    const {
        status,
        setStatus,
        startDate,
        setStartDate,
        endDate,
        setEndDate,
        currentPage,
        pageSize,
        setPageSize,
        records,
        total,
        pages,
        loading,
        syncing,
        error,
        syncedAt,
        snapshotsInserted,
        printLinkLoadingWaybill,
        printLinkMessage,
        fetchReturns,
        runSync,
        requestPrintUrl,
    } = useReturns();

    const isPrintableMode = status === 'printable';

    useEffect(() => {
        if (!isActive) return;
        fetchReturns({ page: 1, persist: true });
    }, [isActive, fetchReturns]);

    const canGoPrev = currentPage > 1;
    const canGoNext = pages > 0 ? currentPage < pages : records.length >= pageSize;

    return html`
        <main className="returns-main">
            <div className="returns-shell">
                <div className="returns-header">
                    <div>
                        <h2>Devoluciones</h2>
                        <p>Consulta en revisión, aprobadas, rechazadas y guías listas para imprimir.</p>
                    </div>

                    <form
                        className="returns-filters"
                        onSubmit=${(event) => {
                            event.preventDefault();
                            fetchReturns({ page: 1, persist: true });
                        }}
                    >
                        <div className="returns-status-selector" role="group" aria-label="Estado de devoluciones">
                            ${[
                                { value: 1, label: 'En revisión' },
                                { value: 2, label: 'Aprobadas' },
                                { value: 3, label: 'Rechazadas' },
                                { value: 'printable', label: 'Para imprimir' },
                            ].map((item) => html`
                                <button
                                    type="button"
                                    className=${`returns-status-btn ${status === item.value ? 'active' : ''}`}
                                    onClick=${() => setStatus(item.value)}
                                    aria-pressed=${status === item.value}
                                >
                                    ${item.label}
                                </button>
                            `)}
                        </div>

                        <label>
                            Tamaño página
                            <select
                                className="form-input"
                                value=${String(pageSize)}
                                onChange=${(event) => setPageSize(Number(event.target.value || 20))}
                            >
                                <option value="20">20</option>
                                <option value="50">50</option>
                                <option value="100">100</option>
                            </select>
                        </label>

                        <${DateRangePicker}
                            label="Rango"
                            dateFrom=${startDate}
                            dateTo=${endDate}
                            onDateChange=${(from, to) => {
                                setStartDate(from);
                                setEndDate(to);
                            }}
                        />

                        <button type="submit" className="form-btn primary" disabled=${loading}>
                            ${loading ? 'Consultando…' : 'Buscar'}
                        </button>
                        <button
                            type="button"
                            className="form-btn outline"
                            onClick=${runSync}
                            disabled=${syncing || isPrintableMode}
                            title=${isPrintableMode ? 'No aplica para la vista de impresión' : ''}
                        >
                            ${syncing ? 'Sincronizando…' : 'Sincronizar'}
                        </button>
                    </form>
                </div>

                <div className="returns-meta">
                    <span>Total: <strong>${total}</strong></span>
                    <span>Estado: <strong>${statusLabel(status)}</strong></span>
                    <span>Insertados en consulta: <strong>${snapshotsInserted}</strong></span>
                    <span>Última sincronización: <strong>${formatDateTimeLabel(syncedAt)}</strong></span>
                </div>

                ${printLinkMessage ? html`<div className="returns-print-message">${printLinkMessage}</div>` : null}

                ${error ? html`<div className="returns-error">${error}</div>` : null}

                <div className="returns-table-wrap">
                    <table className="returns-table">
                        <thead>
                            <tr>
                                <th>Waybill</th>
                                <th>Estado</th>
                                <th>Solicitud</th>
                                <th>Revisión</th>
                                <th>Red</th>
                                <th>Solicitante</th>
                                <th>Motivo</th>
                                <th>Impreso</th>
                                ${isPrintableMode ? html`<th>Acción</th>` : null}
                            </tr>
                        </thead>
                        <tbody>
                            ${records.length === 0
                                ? html`<tr><td colSpan=${isPrintableMode ? '9' : '8'} className="returns-empty">Sin resultados para el filtro actual.</td></tr>`
                                : records.map((row) => html`
                                    <tr key=${`${row.waybill_no}-${row.apply_time}-${row.source_status}`}>
                                        <td>${row.waybill_no || '—'}</td>
                                        <td>${row.status_name || statusLabel(row.source_status)}</td>
                                        <td>${row.apply_time || '—'}</td>
                                        <td>${row.examine_time || '—'}</td>
                                        <td>${row.apply_network_name || row.apply_network_id || '—'}</td>
                                        <td>${row.apply_staff_name || row.apply_staff_code || '—'}</td>
                                        <td>${row.reback_transfer_reason || '—'}</td>
                                        <td>${printFlagLabel(row.print_flag)}</td>
                                        ${isPrintableMode ? html`
                                            <td>
                                                <button
                                                    type="button"
                                                    className="form-btn outline"
                                                    disabled=${printLinkLoadingWaybill === (row.waybill_no || '').toUpperCase()}
                                                    onClick=${async () => {
                                                        const url = await requestPrintUrl(row.waybill_no);
                                                        if (url) window.open(url, '_blank', 'noopener,noreferrer');
                                                    }}
                                                >
                                                    ${printLinkLoadingWaybill === (row.waybill_no || '').toUpperCase() ? 'Generando…' : 'Abrir link'}
                                                </button>
                                            </td>
                                        ` : null}
                                    </tr>
                                `)}
                        </tbody>
                    </table>
                </div>

                <div className="returns-pagination">
                    <button
                        type="button"
                        className="form-btn outline"
                        onClick=${() => fetchReturns({ page: currentPage - 1, persist: true })}
                        disabled=${loading || !canGoPrev}
                    >
                        ← Anterior
                    </button>
                    <span>Página ${currentPage}${pages > 0 ? ` de ${pages}` : ''}</span>
                    <button
                        type="button"
                        className="form-btn outline"
                        onClick=${() => fetchReturns({ page: currentPage + 1, persist: true })}
                        disabled=${loading || !canGoNext}
                    >
                        Siguiente →
                    </button>
                </div>
            </div>
        </main>
    `;
}
