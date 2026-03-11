import { html, createPortal, useEffect, useCallback } from '../../lib/ui.js';
import { useMessengerReport } from '../../hooks/useMessengerReport.js';
import DateRangePicker from '../shared/DateRangePicker.js';

function PrintableReport({ data, totals, dateFrom, dateTo }) {
    if (!data || !data.length || typeof document === 'undefined') return null;
    const host = document.getElementById('print-root') || document.body;
    return createPortal(html`
        <div id="print-table-report">
            <h2>Informe de Mensajeros</h2>
            <p><strong>Periodo:</strong> ${dateFrom} a ${dateTo}</p>
            <p><strong>Mensajeros:</strong> ${data.length}</p>
            <table>
                <thead>
                    <tr>
                        <th>Mensajero</th>
                        <th>Código</th>
                        <th>Asignados</th>
                        <th>Entregados</th>
                        <th>Pendientes</th>
                        <th>Efectividad</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map((r) => html`<tr key=${r.accountCode}>
                        <td>${r.accountName}</td>
                        <td>${r.accountCode}</td>
                        <td>${r.error ? '-' : r.dispatchTotal}</td>
                        <td>${r.error ? '-' : r.signTotal}</td>
                        <td>${r.error ? '-' : r.nosignTotal}</td>
                        <td>${r.error ? html`<span style=${{ color: 'red' }}>Error</span>` : r.effectiveness}</td>
                    </tr>`)}
                    <tr style=${{ fontWeight: 'bold', borderTop: '2px solid #000' }}>
                        <td colspan="2">TOTAL</td>
                        <td>${totals.dispatchTotal}</td>
                        <td>${totals.signTotal}</td>
                        <td>${totals.nosignTotal}</td>
                        <td>${totals.effectiveness}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    `, host);
}

export default function MessengerReportSection() {
    const {
        searchTerm,
        setSearchTerm,
        searchResults,
        dropdownOpen,
        selectedMessengers,
        addMessenger,
        removeMessenger,
        clearMessengers,
        reportDateFrom,
        setReportDateFrom,
        reportDateTo,
        setReportDateTo,
        reportData,
        reportLoading,
        reportError,
        generateReport,
        totals,
        exportCSV
    } = useMessengerReport();

    const handlePrint = useCallback(() => {
        if (!reportData.length) return;
        document.body.classList.add('printing-table');
        setTimeout(() => {
            window.print();
            document.body.classList.remove('printing-table');
        }, 150);
    }, [reportData]);

    useEffect(() => {
        const onAfterPrint = () => document.body.classList.remove('printing-table');
        window.addEventListener('afterprint', onAfterPrint);
        return () => window.removeEventListener('afterprint', onAfterPrint);
    }, []);

    return html`
        <div className="report-section">
            <section className="search-module">
                <div className="search-bar-container">
                    <label>Agregar Mensajero:</label>
                    <input
                        type="text"
                        value=${searchTerm}
                        onChange=${(e) => setSearchTerm(e.target.value)}
                        placeholder="Buscar por Nombre, Apellido o Código..."
                        autoComplete="off"
                    />
                    ${dropdownOpen
                        ? html`<ul className="autocomplete-dropdown">
                            ${searchResults.map((result) => html`<li
                                key=${result.accountCode}
                                onMouseDown=${() => addMessenger(result)}
                            >
                                ${result.accountName} - ${result.accountCode} (${result.customerNetworkName || 'Desconocido'})
                            </li>`)}
                        </ul>`
                        : null}
                </div>
                <${DateRangePicker}
                    dateFrom=${reportDateFrom}
                    dateTo=${reportDateTo}
                    onDateChange=${(start, end) => {
                        setReportDateFrom(start);
                        setReportDateTo(end);
                    }}
                />
            </section>

            ${selectedMessengers.length > 0 ? html`
                <div className="messenger-chips">
                    ${selectedMessengers.map((m) => html`
                        <span key=${m.accountCode} className="chip">
                            ${m.accountName}
                            <button type="button" className="chip-remove" onClick=${() => removeMessenger(m.accountCode)} title="Quitar">×</button>
                        </span>
                    `)}
                    <button type="button" className="chip-clear" onClick=${clearMessengers}>Limpiar todo</button>
                </div>
            ` : null}

            <div className="report-actions no-print">
                <button
                    type="button"
                    className="primary-btn"
                    onClick=${generateReport}
                    disabled=${!selectedMessengers.length || reportLoading}
                >
                    ${reportLoading ? 'Generando…' : 'Generar Informe'}
                </button>
            </div>

            ${reportError ? html`<div className="dash-error">${reportError}</div>` : null}

            ${reportData.length > 0 ? html`
                <section className="table-container">
                    <table className="mobile-card-table report-table">
                        <thead>
                            <tr>
                                <th>Mensajero</th>
                                <th>Código</th>
                                <th>Asignados</th>
                                <th>Entregados</th>
                                <th>Pendientes</th>
                                <th>Efectividad</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${reportData.map((r) => html`<tr key=${r.accountCode} className=${r.error ? 'row-error' : ''}>
                                <td data-label="Mensajero">${r.accountName}</td>
                                <td data-label="Código">${r.accountCode}</td>
                                <td data-label="Asignados">${r.error ? '-' : r.dispatchTotal}</td>
                                <td data-label="Entregados">${r.error ? '-' : r.signTotal}</td>
                                <td data-label="Pendientes">${r.error ? '-' : r.nosignTotal}</td>
                                <td data-label="Efectividad">${r.error
                                    ? html`<span className="error-text" title=${r.error}>Error</span>`
                                    : r.effectiveness}</td>
                            </tr>`)}
                            <tr className="report-totals-row">
                                <td data-label="Mensajero" colspan="2"><strong>TOTAL</strong></td>
                                <td data-label="Asignados"><strong>${totals.dispatchTotal}</strong></td>
                                <td data-label="Entregados"><strong>${totals.signTotal}</strong></td>
                                <td data-label="Pendientes"><strong>${totals.nosignTotal}</strong></td>
                                <td data-label="Efectividad"><strong>${totals.effectiveness}</strong></td>
                            </tr>
                        </tbody>
                    </table>
                </section>
                <div className="report-export-bar no-print">
                    <button type="button" className="secondary-btn" onClick=${handlePrint}>
                        🖨️ Imprimir PDF
                    </button>
                    <button type="button" className="secondary-btn" onClick=${exportCSV}>
                        📥 Descargar CSV
                    </button>
                </div>
            ` : html`
                ${!reportLoading && selectedMessengers.length > 0 ? html`
                    <div className="dash-placeholder">Selecciona las fechas y haz clic en "Generar Informe".</div>
                ` : null}
                ${!reportLoading && !selectedMessengers.length ? html`
                    <div className="dash-placeholder">Busca y selecciona mensajeros para generar un informe grupal.</div>
                ` : null}
            `}

            <${PrintableReport}
                data=${reportData}
                totals=${totals}
                dateFrom=${reportDateFrom}
                dateTo=${reportDateTo}
            />
        </div>
    `;
}
