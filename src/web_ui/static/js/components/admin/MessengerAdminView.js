import { html, createPortal, useEffect, useState } from '../../lib/ui.js';
import { useMessengerAdmin } from '../../hooks/useMessengerAdmin.js';
import { formatDateToSpanish, formatCity, formatCurrencyCOP } from '../../utils/formatters.js';
import { STATUS_DICTIONARY } from '../../utils/constants.js';
import { fetchMessengerContact } from '../../services/messengerService.js';
import DateRangePicker from '../shared/DateRangePicker.js';

function renderMessengerRow(messenger, phoneState) {
    if (!messenger) {
        return html`<tr>
            <td colspan="5" className="table-placeholder">Usa el buscador para encontrar mensajeros…</td>
        </tr>`;
    }
    const statusColor = messenger.status === 1 ? '#56d364' : '#ff7b72';
    let statusText = messenger.statusName || 'Desconocido';
    if (statusText === '启用') statusText = 'Activo';
    if (statusText === '停用') statusText = 'Inactivo';
    const { phone, loading: phoneLoading } = phoneState || {};
    const phoneDisplay = phoneLoading
        ? 'Buscando…'
        : phone
            ? phone
            : 'No disponible';
    return html`<tr>
        <td data-label="Nombre">
            <div className="messenger-name">${messenger.accountName}</div>
        </td>
        <td data-label="Código"><span className="mono">${messenger.accountCode}</span></td>
        <td data-label="Teléfono">
            <span className="messenger-phone ${phone ? 'has-phone' : ''}">
                ${phone ? html`<a href="tel:${phone}">${phoneDisplay}</a>` : phoneDisplay}
            </span>
        </td>
        <td data-label="Punto de Red">${messenger.customerNetworkName || 'N/A'}</td>
        <td data-label="Estado">
            <span className="status-pill" style=${{ color: statusColor }}>${statusText}</span>
        </td>
    </tr>`;
}

function renderMetricsTable(detail, onSelectDay) {
    if (!detail || detail.length === 0) {
        return html`<div className="dash-placeholder">No hay actividad registrada.</div>`;
    }
    const sorted = [...detail].sort((a, b) => new Date(b.dispatchTime) - new Date(a.dispatchTime));
    return html`
        <div className="daily-table">
            <h4>Desglose Diario</h4>
            <table className="mobile-card-table">
                <thead>
                    <tr>
                        <th>Fecha</th>
                        <th>Asignados</th>
                        <th>Entregados</th>
                        <th>Pendientes</th>
                        <th>Efectividad</th>
                    </tr>
                </thead>
                <tbody>
                    ${sorted.map((row) => {
        const total = row.dispatchTotal || 0;
        const delivered = row.signTotal || 0;
        const pending = row.nosignTotal || 0;
        const rate = total ? ((delivered / total) * 100).toFixed(2) + '%' : '0%';
        return html`<tr key=${row.dispatchTime} onClick=${() => onSelectDay(row.dispatchTime.split(' ')[0])}>
                            <td data-label="Fecha">${row.dispatchTime}</td>
                            <td data-label="Asignados">${total}</td>
                            <td data-label="Entregados" className="success-text">${delivered}</td>
                            <td data-label="Pendientes" className="warning-text">${pending}</td>
                            <td data-label="Efectividad">${rate}</td>
                        </tr>`;
    })}
                </tbody>
            </table>
            <div className="table-actions">
                <button type="button" className="secondary-btn" onClick=${() => onSelectDay(null)}>Ver Paquetes de TODO el Periodo</button>
            </div>
        </div>
    `;
}

function renderWaybillsTable(state) {
    const {
        list,
        totalCount,
        loading,
        error,
        onExport,
        showPendingOnly,
        onTogglePending,
        visibleDelivered,
        visiblePending
    } = state;
    if (!totalCount && !loading && !error) {
        return null;
    }
    const sortedList = list ? [...list].sort((a, b) => new Date(b.dispatchTime || 0) - new Date(a.dispatchTime || 0)) : [];
    const hasRows = sortedList.length > 0;
    const emptyMessage = totalCount
        ? showPendingOnly
            ? 'No hay paquetes pendientes en el rango seleccionado.'
            : 'No se detectaron guías para este período.'
        : 'Selecciona un mensajero para ver los paquetes.';

    return html`
        <div className="waybills-panel">
            <div className="waybills-header">
                <div>
                    <h4>Detalle de Paquetes Asignados</h4>
                    <p>
                        Total: <strong>${totalCount}</strong>
                        · Visibles: <strong>${sortedList.length}</strong>
                        · Entregados: <strong className="success-text">${visibleDelivered}</strong>
                        · Pendientes: <strong className="warning-text">${visiblePending}</strong>
                    </p>
                </div>
                <button type="button" className="primary-btn" onClick=${onExport} disabled=${!totalCount}>Descargar PDF</button>
            </div>
            <div className="waybills-controls">
                <span className="controls-label">Vista rápida:</span>
                <button
                    type="button"
                    className=${showPendingOnly ? 'filter-pill active' : 'filter-pill'}
                    onClick=${onTogglePending}
                >
                    ${showPendingOnly ? 'Ver todos los paquetes' : 'Solo pendientes'}
                </button>
                <span className="controls-caption">
                    ${showPendingOnly ? 'Mostrando únicamente paquetes sin firma' : 'Incluye entregas y pendientes'}
                </span>
            </div>
            ${loading
                ? html`<div className="dash-placeholder">Cargando paquetes…</div>`
                : error
                    ? html`<div className="dash-error">${error}</div>`
                    : hasRows
                        ? html`
                            <div className="table-scroll">
                                <table className="mobile-card-table">
                                    <thead>
                                        <tr>
                                            <th>Guía</th>
                                            <th>Fecha Despacho</th>
                                            <th>Ciudad/Destino</th>
                                            <th>Estado</th>
                                            <th>Fecha Entrega</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${sortedList.map((item) => {
        const deliveredNow = item.isSign === 1;
        const translatedStatus = STATUS_DICTIONARY[item.status] || item.status;
        return html`<tr key=${item.waybillNo}>
                                                <td data-label="Guía">
                                                    <span className="waybill-link">${item.waybillNo}</span>
                                                </td>
                                                <td data-label="Despacho">${item.dispatchTime || 'N/A'}</td>
                                                <td data-label="Ciudad">${formatCity(item.receiverCitye)}</td>
                                                <td data-label="Estado" className=${deliveredNow ? 'success-text' : 'warning-text'}>${translatedStatus}</td>
                                                    <td data-label="Entrega">${item.signTime || 'N/A'}</td>
                                                </tr>`;
        })}
                                        </tbody>
                                    </table>
                                </div>
                            `
                            : html`<div className="waybills-empty">${emptyMessage}</div>`}
            </div>
        `;
    }

    function ExportModal({
        open,
        groupedDays,
        selectedDates,
        toggleDateSelection,
        onlyPending,
        setOnlyPending,
        exportStats,
        onClose,
        onConfirm
    }) {
        if (!open) return null;
        const entries = Object.entries(groupedDays || {}).sort(([a], [b]) => {
            if (a === 'Desconocido') return 1;
            if (b === 'Desconocido') return -1;
            return new Date(b) - new Date(a);
        });
        return html`
            <div className="modal-overlay">
            <div className="modal-content">
                <div className="modal-header">
                    <h3>Exportar Reporte de Paquetes</h3>
                    <button type="button" className="modal-close" onClick=${onClose}>×</button>
                </div>
                <div className="modal-body">
                    <div className="modal-switch">
                        <label>
                            <input type="checkbox" checked=${onlyPending} onChange=${(e) => setOnlyPending(e.target.checked)} />
                            Solo Pendientes
                        </label>
                    </div>
                    <div className="modal-day-list">
                        ${entries.map(([day, stats]) => html`<label key=${day}>
                            <input
                                type="checkbox"
                                checked=${selectedDates.has(day)}
                                onChange=${() => toggleDateSelection(day)}
                            />
                            ${day}
                            <span className="day-meta">(Entregados: ${stats.delivered}, Pendientes: ${stats.pending})</span>
                        </label>`)}
                    </div>
                    <div className="modal-stats">
                        <div>Entregados: <strong>${onlyPending ? '0 (omitidos)' : exportStats.delivered}</strong></div>
                        <div>Pendientes: <strong>${exportStats.pending}</strong></div>
                    </div>
                </div>
                <div className="modal-actions">
                    <button type="button" className="secondary-btn" onClick=${onClose}>Cancelar</button>
                    <button type="button" className="primary-btn" onClick=${onConfirm}>Imprimir PDF</button>
                </div>
            </div>
        </div>
    `;
}

function PrintReport({ payload }) {
    if (!payload || typeof document === 'undefined') return null;
    const host = document.getElementById('print-root') || document.body;
    return createPortal(html`
        <div id="print-table-report">
            <h2>Reporte de Paquetes - ${payload.messengerName}</h2>
            <p><strong>Días incluidos:</strong> ${payload.selectedDates.join(', ')}</p>
            ${payload.onlyPending
            ? html`<p className="warning-text">MODO: SOLO PAQUETES PENDIENTES</p>`
            : null}
            <p><strong>Total Entregados en PDF:</strong> ${payload.delivered}</p>
            <p><strong>Total Pendientes en PDF:</strong> ${payload.pending}</p>
            <table>
                <thead>
                    <tr>
                        <th>Guía</th>
                        <th>Fecha Despacho</th>
                        <th>Destino</th>
                        <th>Estado</th>
                        <th>${payload.onlyPending ? 'Dirección' : 'Fecha Entrega'}</th>
                    </tr>
                </thead>
                <tbody>
                    ${payload.rows.map((row) => html`<tr key=${row.waybillNo}>
                        <td>${row.waybillNo}</td>
                        <td>${formatDateToSpanish(row.dispatchTime)}</td>
                        <td>${formatCity(row.city)}</td>
                        <td>${row.status}</td>
                        <td>${payload.onlyPending ? row.address || 'Enrutado a destino regional' : formatDateToSpanish(row.signTime)}</td>
                    </tr>`)}
                </tbody>
            </table>
        </div>
    `, host);
}

function toDigits(value) {
    return String(value || '').replace(/\D/g, '');
}

function normalizeMoneyInput(value) {
    const digits = toDigits(value).replace(/^0+(?=\d)/, '');
    return digits;
}

function formatMoneyWithDots(value) {
    const normalized = normalizeMoneyInput(value);
    if (!normalized) return '';
    return normalized.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

export default function MessengerAdminView() {
    const state = useMessengerAdmin();
    const {
        searchTerm,
        setSearchTerm,
        searchResults,
        dropdownOpen,
        handleSelectMessenger,
        selectedMessenger,
        dateFrom,
        setDateFrom,
        dateTo,
        setDateTo,
        metricsSummary,
        metricsDetail,
        metricsLoading,
        metricsError,
        requestWaybills,
        waybills,
        waybillsLoading,
        waybillsError,
        openExportModal,
        modalOpen,
        setModalOpen,
        selectedDates,
        toggleDateSelection,
        setSelectedDates,
        onlyPending,
        setOnlyPending,
        exportStats,
        confirmExport,
        groupedWaybillDays,
        filteredWaybills,
        showPendingOnly,
        setShowPendingOnly,
        visibleDelivered,
        visiblePending,
        printPayload,
        metricsCards,
        ratePerDelivery,
        setRatePerDelivery,
        deductionPerIssue,
        setDeductionPerIssue,
        settlementLoading,
        settlementError,
        latestSettlement,
        settlementHistory,
        saveRate,
        generateCurrentSettlement,
        removeSettlement
    } = state;
    const [deleteTarget, setDeleteTarget] = useState(null);
    const [viewMode, setViewMode] = useState('individual');
    const [messengerPhone, setMessengerPhone] = useState('');
    const [phoneLoading, setPhoneLoading] = useState(false);

    useEffect(() => {
        if (!selectedMessenger) {
            setMessengerPhone('');
            return;
        }
        setPhoneLoading(true);
        setMessengerPhone('');
        fetchMessengerContact(
            selectedMessenger.accountName,
            selectedMessenger.customerNetworkCode || ''
        )
            .then((data) => setMessengerPhone(data?.phone || ''))
            .catch(() => setMessengerPhone(''))
            .finally(() => setPhoneLoading(false));
    }, [selectedMessenger]);

    const totalWaybills = waybills.length;
    const filteredList = filteredWaybills;
    const handleTogglePendingView = () => setShowPendingOnly((prev) => !prev);

    const handleDaySelection = (day) => {
        if (!selectedMessenger) return;
        if (day) {
            requestWaybills(selectedMessenger, day, day);
        } else {
            requestWaybills(selectedMessenger, dateFrom, dateTo);
        }
    };

    useEffect(() => {
        const handleMessengerFromSearch = (event) => {
            const messenger = event?.detail?.messenger;
            if (!messenger) return;
            handleSelectMessenger(messenger);
        };

        window.addEventListener('open-messenger-from-search', handleMessengerFromSearch);
        return () => {
            window.removeEventListener('open-messenger-from-search', handleMessengerFromSearch);
        };
    }, [handleSelectMessenger]);

    return html`
        <main className="admin-main">
            <header className="header no-print">
                <h2>Administración de Mensajeros</h2>
                <p className="subtitle">Busca y consulta información sobre el personal de reparto.</p>
                <div className="mode-toggle">
                    <button type="button" className=${`filter-pill ${viewMode === 'individual' ? 'active' : ''}`} onClick=${() => setViewMode('individual')}>Individual</button>
                    <button type="button" className=${`filter-pill ${viewMode === 'report' ? 'active' : ''}`} onClick=${() => setViewMode('report')}>Informe Grupal</button>
                </div>
            </header>
            ${viewMode === 'report' ? html`<${MessengerReportSection} />` : html`
            <section className="search-module">
                <div className="search-bar-container">
                    <label>Buscar Mensajero:</label>
                    <input
                        type="text"
                        value=${searchTerm}
                        onChange=${(e) => setSearchTerm(e.target.value)}
                        placeholder="Buscar por Nombre, Apellido o Código..."
                        autoComplete="off"
                    />
                    ${dropdownOpen
            ? html`<ul className="autocomplete-dropdown">
                            ${searchResults.map((result) => html`<li key=${result.accountCode} onMouseDown=${() => handleSelectMessenger(result)}>
                                ${result.accountName} - ${result.accountCode} (${result.customerNetworkName || 'Desconocido'})
                            </li>`)}
                        </ul>`
            : null}
                </div>
                <${DateRangePicker} 
                    dateFrom=${dateFrom} 
                    dateTo=${dateTo} 
                    onDateChange=${(start, end) => {
                        setDateFrom(start);
                        setDateTo(end);
                    }} 
                />
            </section>
            ${selectedMessenger ? html`
            <section className="table-container">
                <table className="mobile-card-table messenger-info-table">
                    <thead>
                        <tr>
                            <th>Nombre / Cuenta</th>
                            <th>Código de Red</th>
                            <th>Teléfono</th>
                            <th>Punto de Red</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${renderMessengerRow(selectedMessenger, { phone: messengerPhone, loading: phoneLoading })}
                    </tbody>
                </table>
            </section>
            ` : null}
            <section className="dashboard-container" style=${{ display: selectedMessenger ? 'block' : 'none' }}>
                <h3>Métricas de Desempeño</h3>
                ${metricsLoading
            ? html`<div className="dash-placeholder">Cargando métricas…</div>`
            : metricsError
                ? html`<div className="dash-error">${metricsError}</div>`
                : html`<div className="dashboard-grid">
                            ${metricsCards.map((card) => html`<div key=${card.title} className="kpi-card">
                                <span className="kpi-label">${card.title}</span>
                                <span className="kpi-value" style=${{ color: card.accent }}>${card.value}</span>
                            </div>`)}
                        </div>`}
                ${renderMetricsTable(metricsDetail, handleDaySelection)}
            </section>
            ${selectedMessenger ? html`
                <section className="dashboard-container settlement-panel">
                    <h3>Liquidación de Mensajero (MVP)</h3>
                    <p className="subtitle">Tarifa fija por entrega firmada en el rango seleccionado.</p>
                    <p className="subtitle">Estado <strong>borrador</strong>: liquidación generada, pendiente de aprobación/pago.</p>

                    <div className="settlement-controls">
                        <label>
                            Tarifa por entrega
                            <input
                                type="text"
                                inputMode="numeric"
                                value=${formatMoneyWithDots(ratePerDelivery)}
                                placeholder="0"
                                onChange=${(e) => setRatePerDelivery(normalizeMoneyInput(e.target.value))}
                            />
                        </label>
                        <label>
                            Descuento por novedad pendiente
                            <input
                                type="text"
                                inputMode="numeric"
                                value=${formatMoneyWithDots(deductionPerIssue)}
                                placeholder="0"
                                onChange=${(e) => setDeductionPerIssue(normalizeMoneyInput(e.target.value))}
                            />
                        </label>
                        <div className="settlement-actions">
                            <button type="button" className="secondary-btn settlement-secondary-btn" onClick=${saveRate} disabled=${settlementLoading}>
                                Guardar tarifa
                            </button>
                            <button type="button" className="primary-btn settlement-primary-btn" onClick=${generateCurrentSettlement} disabled=${settlementLoading}>
                                ${settlementLoading ? 'Generando…' : 'Generar liquidación'}
                            </button>
                        </div>
                    </div>

                    ${settlementError ? html`<div className="dash-error">${settlementError}</div>` : null}

                    ${latestSettlement ? html`
                        <div className="settlement-summary">
                            <div><span>Total guías</span><strong>${latestSettlement.total_waybills}</strong></div>
                            <div><span>Entregadas</span><strong className="success-text">${latestSettlement.total_delivered}</strong></div>
                            <div><span>Pendientes</span><strong className="warning-text">${latestSettlement.total_pending}</strong></div>
                            <div><span>Deducciones</span><strong>${formatCurrencyCOP(latestSettlement.deduction_total)}</strong></div>
                            <div><span>Neto a pagar</span><strong>${formatCurrencyCOP(latestSettlement.total_amount)}</strong></div>
                        </div>
                    ` : null}

                    <div className="daily-table settlement-history">
                        <h4>Historial reciente</h4>
                        <table className="mobile-card-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Periodo</th>
                                    <th>Entregadas</th>
                                    <th>Deducciones</th>
                                    <th>Total</th>
                                    <th>Estado</th>
                                    <th>Acciones</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${settlementHistory.length
            ? settlementHistory.map((item) => html`<tr key=${item.id}>
                                            <td data-label="ID">#${item.id}</td>
                                            <td data-label="Periodo">${item.start_time?.split(' ')[0]} → ${item.end_time?.split(' ')[0]}</td>
                                            <td data-label="Entregadas">${item.total_delivered}</td>
                                            <td data-label="Deducciones">${formatCurrencyCOP(item.deduction_total)}</td>
                                            <td data-label="Total">${formatCurrencyCOP(item.total_amount)}</td>
                                            <td data-label="Estado">${item.status}</td>
                                            <td data-label="">
                                                <button
                                                    type="button"
                                                    className="secondary-btn danger-btn"
                                                    onClick=${() => setDeleteTarget(item.id)}
                                                    disabled=${settlementLoading}
                                                >
                                                    Eliminar
                                                </button>
                                            </td>
                                        </tr>`)
            : html`<tr><td colspan="7" className="table-placeholder">Sin liquidaciones generadas aún.</td></tr>`}
                            </tbody>
                        </table>
                    </div>
                </section>
            ` : null}
            ${renderWaybillsTable({
                    list: filteredList,
                    totalCount: totalWaybills,
                    loading: waybillsLoading,
                    error: waybillsError,
                    onExport: openExportModal,
                    showPendingOnly,
                    onTogglePending: handleTogglePendingView,
                    visibleDelivered,
                    visiblePending
                })}
            <${ExportModal}
                open=${modalOpen}
                groupedDays=${groupedWaybillDays}
                selectedDates=${selectedDates}
                toggleDateSelection=${toggleDateSelection}
                onlyPending=${onlyPending}
                setOnlyPending=${setOnlyPending}
                exportStats=${exportStats}
                onClose=${() => {
            setModalOpen(false);
            setSelectedDates(new Set());
        }}
                onConfirm=${confirmExport}
            />
            <${PrintReport} payload=${printPayload} />
            ${deleteTarget ? html`
                <div className="modal-overlay" onClick=${() => setDeleteTarget(null)}>
                    <div className="modal-content settlement-confirm-modal" onClick=${(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>Eliminar liquidación</h3>
                            <button type="button" className="modal-close" onClick=${() => setDeleteTarget(null)}>×</button>
                        </div>
                        <div className="modal-body">
                            <p>¿Seguro que deseas eliminar la liquidación #${deleteTarget}? Esta acción no se puede deshacer.</p>
                        </div>
                        <div className="modal-actions">
                            <button type="button" className="secondary-btn settlement-secondary-btn" onClick=${() => setDeleteTarget(null)}>
                                Cancelar
                            </button>
                            <button
                                type="button"
                                className="primary-btn settlement-primary-btn danger-solid"
                                onClick=${async () => {
                                    const current = deleteTarget;
                                    setDeleteTarget(null);
                                    await removeSettlement(current);
                                }}
                            >
                                Eliminar
                            </button>
                        </div>
                    </div>
                </div>
            ` : null}            `}        </main>
    `;
}
