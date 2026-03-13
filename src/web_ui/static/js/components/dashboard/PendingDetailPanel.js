import { html } from '../../lib/ui.js';
import { formatShortDate } from '../../utils/formatters.js';
import {
    EXPORTABLE_FIELDS,
    getWaybillId,
    getReceiverName,
    getReceiverCity,
    getReceiverAddress,
    getPhoneButtonLabel,
    getPackageDateByMode,
    getPackageStatus
} from '../../utils/pendingHelpers.js';

export default function PendingDetailPanel({
    selectedCell,
    activeDateLabel,
    showExportMenu,
    setShowExportMenu,
    exportFields,
    toggleExportField,
    handleExportPdf,
    exportJsonLoading,
    handleExportJson,
    exportJsonError,
    setSelectedCell,
    detailLoading,
    detailError,
    detailRows,
    detailMap,
    phoneState,
    handlePhoneClick,
    dateMode,
    dateModes
}) {
    if (!selectedCell) return null;

    return html`
        <section className="dash-detail-panel">
            <div className="dash-detail-header">
                <div>
                    <h3>${selectedCell.staff}</h3>
                    <p>${activeDateLabel}: ${selectedCell.day === 'ALL' ? 'Todos los días' : selectedCell.day === 'Sin Fecha' ? 'Sin fecha registrada' : formatShortDate(selectedCell.day)}</p>
                    <p>Total paquetes: ${selectedCell.records.length}</p>
                </div>
                <div className="dash-detail-actions">
                    <div className="dash-export-menu-wrap">
                        <button
                            type="button"
                            className="dash-export-btn"
                            onClick=${() => setShowExportMenu((prev) => !prev)}
                        >
                            Exportar ▾
                        </button>
                        ${showExportMenu
                            ? html`<div className="dash-export-menu">
                                <p className="dash-export-title">Campos para PDF</p>
                                <div className="dash-export-options">
                                    ${EXPORTABLE_FIELDS.map((field) => html`
                                        <label key=${field.key}>
                                            <input
                                                type="checkbox"
                                                checked=${Boolean(exportFields[field.key])}
                                                onChange=${() => toggleExportField(field.key)}
                                            />
                                            <span>${field.label}</span>
                                        </label>
                                    `)}
                                </div>
                                <div className="dash-export-actions">
                                    <button
                                        type="button"
                                        className="primary-btn dash-export-run-btn"
                                        onClick=${handleExportPdf}
                                    >
                                        Descargar PDF
                                    </button>
                                    <button
                                        type="button"
                                        className="secondary-btn dash-export-run-btn"
                                        disabled=${exportJsonLoading}
                                        onClick=${handleExportJson}
                                    >
                                        ${exportJsonLoading ? 'Generando…' : 'Descargar JSON'}
                                    </button>
                                </div>
                                ${exportJsonError ? html`<p className="dash-export-error">${exportJsonError}</p>` : null}
                            </div>`
                            : null}
                    </div>
                    <button type="button" className="secondary-btn" onClick=${() => setSelectedCell(null)}>Cerrar detalle</button>
                </div>
            </div>
            <div className="dash-detail-body">
                ${detailLoading ? html`<p className="dash-detail-hint">Consultando información precisa de las guías…</p>` : null}
                ${detailError ? html`<div className="dash-error dash-detail-error">${detailError}</div>` : null}
                <div className="dash-detail-scroll">
                    ${detailRows.length === 0
                        ? html`<div className="dash-placeholder">Sin paquetes para mostrar.</div>`
                        : html`<table className="dash-detail-table mobile-card-table">
                            <thead>
                                <tr>
                                    <th>Guía</th>
                                    <th>Destinatario</th>
                                    <th>Ciudad</th>
                                    <th>Dirección</th>
                                    <th>Contacto</th>
                                    <th>${activeDateLabel}</th>
                                    <th>Estado</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${detailRows.map((pkg, index) => {
                                    const detail = pkg.waybillNo ? detailMap[pkg.waybillNo] : null;
                                    const phoneInfo = pkg.waybillNo ? phoneState[pkg.waybillNo] : null;
                                    return html`<tr key=${getWaybillId(pkg, index)}>
                                        <td data-label="Guía">${pkg.waybillNo || 'N/A'}</td>
                                        <td data-label="Destinatario">${detail?.receiverName || getReceiverName(pkg)}</td>
                                        <td data-label="Ciudad">${detail?.receiverCity || getReceiverCity(pkg)}</td>
                                        <td data-label="Dirección">${detail?.receiverAddress || getReceiverAddress(pkg)}</td>
                                        <td data-label="Contacto" className="dash-phone-cell">
                                            ${pkg.waybillNo
                                                ? html`<button
                                                    type="button"
                                                    className="dash-phone-btn"
                                                    disabled=${phoneInfo?.loading}
                                                    onClick=${() => handlePhoneClick(pkg.waybillNo)}
                                                >
                                                    ${getPhoneButtonLabel(phoneInfo)}
                                                </button>`
                                                : html`<span className="dash-phone-disabled">N/A</span>`}
                                            ${phoneInfo?.error
                                                ? html`<span className="dash-phone-error">${phoneInfo.error}</span>`
                                                : null}
                                            ${phoneInfo?.value && phoneInfo.visible
                                                ? html`<span className="dash-phone-value">${phoneInfo.value}</span>`
                                                : null}
                                        </td>
                                        <td data-label="Fecha">${getPackageDateByMode(pkg, dateMode, dateModes)}</td>
                                        <td data-label="Estado">${detail?.status || getPackageStatus(pkg)}</td>
                                    </tr>`;
                                })}
                            </tbody>
                        </table>`}
                </div>
            </div>
        </section>
    `;
}
