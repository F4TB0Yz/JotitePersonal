import { html, createPortal, useEffect, useCallback, useState } from '../../lib/ui.js';
import { useMessengerReport } from '../../hooks/useMessengerReport.js';

const ALL_COLUMNS = [
    { key: 'dispatchStaffName', label: 'Mensajero',   getValue: (r) => r.dispatchStaffName,    getTotal: () => '' },
    { key: 'dispatchStaffCode', label: 'Código',      getValue: (r) => r.dispatchStaffCode,    getTotal: () => '' },
    { key: 'dispatchTotal',     label: 'Asignados',   getValue: (r) => r.dispatchTotal,        getTotal: (t) => t.dispatchTotal },
    { key: 'signTotal',         label: 'Entregados',  getValue: (r) => r.signTotal,            getTotal: (t) => t.signTotal },
    { key: 'nosignTotal',       label: 'Pendientes',  getValue: (r) => r.nosignTotal,          getTotal: (t) => t.nosignTotal },
    { key: 'signTotalRate',     label: 'Efectividad', getValue: (r) => r.signTotalRate || '0%', getTotal: (t) => t.effectiveness },
];

function PrintableReport({ data, totals, startDate, endDate, visibleCols }) {
    if (!data || !data.length || typeof document === 'undefined') return null;
    const host = document.getElementById('print-root') || document.body;
    const dateLabel = startDate === endDate ? startDate : `${startDate} al ${endDate}`;
    const cols = ALL_COLUMNS.filter((c) => visibleCols.has(c.key));
    return createPortal(
        html`
            <div id="print-table-report">
                <h2>Informe de Mensajeros — ${dateLabel}</h2>
                <p><strong>Mensajeros seleccionados:</strong> ${data.length}</p>
                <table>
                    <thead>
                        <tr>
                            ${cols.map((c) => html`<th key=${c.key}>${c.label}</th>`)}
                        </tr>
                    </thead>
                    <tbody>
                        ${data.map(
                            (r) => html`<tr key=${r.dispatchStaffCode}>
                                ${cols.map((c) => html`<td key=${c.key}>${c.getValue(r)}</td>`)}
                            </tr>`
                        )}
                        <tr style=${{ fontWeight: 'bold', borderTop: '2px solid #000' }}>
                            ${cols.map((c, i) =>
                                i === 0
                                    ? html`<td key=${c.key} colspan=${cols.length > 1 ? 1 : 1}><strong>TOTAL</strong></td>`
                                    : html`<td key=${c.key}><strong>${c.getTotal(totals)}</strong></td>`
                            )}
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
        startDate,
        setStartDate,
        endDate,
        setEndDate,
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

    const [visibleCols, setVisibleCols] = useState(
        () => new Set(ALL_COLUMNS.map((c) => c.key))
    );
    const [showColPicker, setShowColPicker] = useState(false);

    const toggleCol = useCallback((key) => {
        setVisibleCols((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                if (next.size === 1) return prev; // al menos 1 columna
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    }, []);

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
                    <label class="report-date-label">Desde:</label>
                    <input
                        type="date"
                        class="report-date-input"
                        value=${startDate}
                        onChange=${(e) => {
                            setStartDate(e.target.value);
                            if (endDate < e.target.value) setEndDate(e.target.value);
                        }}
                        max=${new Date().toISOString().split('T')[0]}
                    />
                </div>
                <div class="report-date-field">
                    <label class="report-date-label">Hasta:</label>
                    <input
                        type="date"
                        class="report-date-input"
                        value=${endDate}
                        onChange=${(e) => setEndDate(e.target.value)}
                        min=${startDate}
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
                              <div class="col-picker-wrapper">
                                  <button
                                      type="button"
                                      class="secondary-btn"
                                      onClick=${() => setShowColPicker((v) => !v)}
                                  >
                                      ⚙️ Columnas PDF
                                  </button>
                                  ${showColPicker
                                      ? html`<div class="col-picker-dropdown">
                                            <p class="col-picker-title">Columnas a incluir:</p>
                                            ${ALL_COLUMNS.map(
                                                (c) => html`<label key=${c.key} class="col-picker-item">
                                                    <input
                                                        type="checkbox"
                                                        checked=${visibleCols.has(c.key)}
                                                        onChange=${() => toggleCol(c.key)}
                                                    />
                                                    ${c.label}
                                                </label>`
                                            )}
                                        </div>`
                                      : null}
                              </div>
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
                            Selecciona un rango de fechas y haz clic en "Cargar Mensajeros" para ver el informe.
                        </div>`
                      : null}`}

            <${PrintableReport} data=${selectedRecords} totals=${totals} startDate=${startDate} endDate=${endDate} visibleCols=${visibleCols} />
        </div>
    `;
}
