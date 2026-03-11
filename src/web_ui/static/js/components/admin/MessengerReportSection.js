import { html, createPortal, useEffect, useCallback } from '../../lib/ui.js';
import { useMessengerReport } from '../../hooks/useMessengerReport.js';

function PrintableReport({ data, totals, date }) {
    if (!data || !data.length || typeof document === 'undefined') return null;
    const host = document.getElementById('print-root') || document.body;
    return createPortal(
        html`
            <div id="print-table-report">
                <h2>Informe de Mensajeros — ${date}</h2>
                <p><strong>Mensajeros seleccionados:</strong> ${data.length}</p>
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
                        ${data.map(
                            (r) => html`<tr key=${r.dispatchStaffCode}>
                                <td>${r.dispatchStaffName}</td>
                                <td>${r.dispatchStaffCode}</td>
                                <td>${r.dispatchTotal}</td>
                                <td>${r.signTotal}</td>
                                <td>${r.nosignTotal}</td>
                                <td>${r.signTotalRate || '0%'}</td>
                            </tr>`
                        )}
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
        `,
        host
    );
}

export default function MessengerReportSection() {
    const {
        date,
        setDate,
        records,
        filteredRecords,
        selectedCodes,
        selectedRecords,
        filterText,
        setFilterText,
        loading,
        error,
        loadDay,
        toggleMessenger,
        selectAll,
        deselectAll,
        totals,
        exportCSV,
    } = useMessengerReport();

    const handlePrint = useCallback(() => {
        if (!selectedRecords.length) return;
        document.body.classList.add('printing-table');
        setTimeout(() => {
            window.print();
            document.body.classList.remove('printing-table');
        }, 150);
    }, [selectedRecords]);

    useEffect(() => {
        const onAfterPrint = () => document.body.classList.remove('printing-table');
        window.addEventListener('afterprint', onAfterPrint);
        return () => window.removeEventListener('afterprint', onAfterPrint);
    }, []);

    return html`
        <div class="report-section">
            <div class="report-load-bar">
                <div class="report-date-field">
                    <label class="report-date-label">Fecha:</label>
                    <input
                        type="date"
                        class="report-date-input"
                        value=${date}
                        onChange=${(e) => setDate(e.target.value)}
                        max=${new Date().toISOString().split('T')[0]}
                    />
                </div>
                <button
                    type="button"
                    class="primary-btn"
                    onClick=${loadDay}
                    disabled=${loading}
                >
                    ${loading ? 'Cargando…' : 'Cargar Mensajeros'}
                </button>
            </div>

            ${error ? html`<div class="dash-error">${error}</div>` : null}

            ${records.length > 0
                ? html`
                    <div class="report-controls">
                        <input
                            type="text"
                            class="report-filter-input"
                            placeholder="Filtrar mensajero…"
                            value=${filterText}
                            onInput=${(e) => setFilterText(e.target.value)}
                        />
                        <div class="report-select-btns">
                            <button type="button" class="secondary-btn sm-btn" onClick=${selectAll}>
                                Todos (${records.length})
                            </button>
                            <button type="button" class="secondary-btn sm-btn" onClick=${deselectAll}>
                                Ninguno
                            </button>
                            <span class="report-selected-count">${selectedCodes.size} seleccionados</span>
                        </div>
                    </div>

                    <section class="table-container">
                        <table class="mobile-card-table report-table">
                            <thead>
                                <tr>
                                    <th class="col-check"></th>
                                    <th>Mensajero</th>
                                    <th>Código</th>
                                    <th>Asignados</th>
                                    <th>Entregados</th>
                                    <th>Pendientes</th>
                                    <th>Efectividad</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${filteredRecords.map((r) => {
                                    const isSelected = selectedCodes.has(r.dispatchStaffCode);
                                    return html`<tr
                                        key=${r.dispatchStaffCode}
                                        class=${isSelected ? 'row-selected' : 'row-unselected'}
                                        onClick=${() => toggleMessenger(r.dispatchStaffCode)}
                                        style=${{ cursor: 'pointer' }}
                                    >
                                        <td class="col-check">
                                            <input
                                                type="checkbox"
                                                checked=${isSelected}
                                                onChange=${() => toggleMessenger(r.dispatchStaffCode)}
                                                onClick=${(e) => e.stopPropagation()}
                                            />
                                        </td>
                                        <td data-label="Mensajero">${r.dispatchStaffName}</td>
                                        <td data-label="Código">${r.dispatchStaffCode}</td>
                                        <td data-label="Asignados">${r.dispatchTotal}</td>
                                        <td data-label="Entregados">${r.signTotal}</td>
                                        <td data-label="Pendientes">${r.nosignTotal}</td>
                                        <td data-label="Efectividad">${r.signTotalRate || '0%'}</td>
                                    </tr>`;
                                })}
                                ${selectedCodes.size > 0
                                    ? html`<tr class="report-totals-row">
                                          <td></td>
                                          <td colspan="2"><strong>TOTAL (${selectedCodes.size})</strong></td>
                                          <td><strong>${totals.dispatchTotal}</strong></td>
                                          <td><strong>${totals.signTotal}</strong></td>
                                          <td><strong>${totals.nosignTotal}</strong></td>
                                          <td><strong>${totals.effectiveness}</strong></td>
                                      </tr>`
                                    : null}
                            </tbody>
                        </table>
                    </section>

                    ${selectedCodes.size > 0
                        ? html`<div class="report-export-bar no-print">
                              <button type="button" class="secondary-btn" onClick=${handlePrint}>
                                  🖨️ Imprimir PDF
                              </button>
                              <button type="button" class="secondary-btn" onClick=${exportCSV}>
                                  📥 Descargar CSV
                              </button>
                          </div>`
                        : null}
                  `
                : html`${!loading
                      ? html`<div class="dash-placeholder">
                            Selecciona una fecha y haz clic en "Cargar Mensajeros" para ver el informe del día.
                        </div>`
                      : null}`}

            <${PrintableReport} data=${selectedRecords} totals=${totals} date=${date} />
        </div>
    `;
}
