import { html, useState } from '../../lib/ui.js';
import { useDailyReport } from '../../hooks/useDailyReport.js';

const ALL_PRINT_COLS = [
    { key: 'messenger', label: 'Mensajero',  getValue: (e) => e.messenger_name || '—' },
    { key: 'address',   label: 'Dirección',  getValue: (e) => e.address || '—' },
    { key: 'city',      label: 'Ciudad',     getValue: (e) => e.city || '—' },
    { key: 'status',    label: 'Estado',     getValue: (e) => e.status || '—' },
    { key: 'notes',     label: 'Notas',      getValue: (e) => e.notes || '' },
    { key: 'date',      label: 'Fecha',      getValue: (e) => e.report_date },
];

function PrintPreviewModal({ groupedEntries, startDate, endDate, groupBy, onClose }) {
    const today = new Date().toLocaleDateString('es-CO', {
        year: 'numeric', month: 'long', day: 'numeric',
    });

    const [visibleCols, setVisibleCols] = useState(
        () => new Set(['messenger', 'address', 'city', 'status', 'notes'])
    );
    const [showColPicker, setShowColPicker] = useState(false);

    const toggleCol = (key) => {
        setVisibleCols((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                if (next.size === 1) return prev;
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    };

    const handlePrint = () => {
        setShowColPicker(false);
        setTimeout(() => window.print(), 50);
    };

    const groupLabel = groupBy === 'messenger'
        ? 'Agrupado por mensajero'
        : groupBy === 'city'
            ? 'Agrupado por ciudad'
            : 'Sin agrupar';

    const total = groupedEntries.reduce((s, g) => s + g.items.length, 0);
    const activeCols = ALL_PRINT_COLS.filter((c) => visibleCols.has(c.key));

    return html`
        <div className="dr-preview-overlay" onClick=${onClose}>
            <div className="dr-preview-modal" onClick=${(e) => e.stopPropagation()}>
                <header className="dr-preview-header no-print">
                    <div className="dr-preview-header-info">
                        <h3>Vista previa — Reporte diario</h3>
                        <span className="dr-preview-meta">
                            ${startDate === endDate ? startDate : startDate + ' → ' + endDate} · ${groupLabel}
                        </span>
                    </div>
                    <div className="dr-preview-header-actions">
                        <div className="dr-col-picker-wrapper">
                            <button
                                type="button"
                                className="dr-col-picker-btn"
                                onClick=${() => setShowColPicker((v) => !v)}
                            >⚙️ Columnas</button>
                            ${showColPicker ? html`
                                <div className="dr-col-picker-dropdown">
                                    <p className="dr-col-picker-title">Columnas en el PDF:</p>
                                    ${ALL_PRINT_COLS.map((c) => html`
                                        <label key=${c.key} className="dr-col-picker-item">
                                            <input
                                                type="checkbox"
                                                checked=${visibleCols.has(c.key)}
                                                onChange=${() => toggleCol(c.key)}
                                            />
                                            ${c.label}
                                        </label>
                                    `)}
                                </div>
                            ` : null}
                        </div>
                        <button type="button" className="dr-print-btn" onClick=${handlePrint}>
                            🖨️ Imprimir / PDF
                        </button>
                        <button type="button" className="dr-close-btn" onClick=${onClose}>✕</button>
                    </div>
                </header>

                <div className="dr-preview-body" id="daily-report-printable">
                    <div className="dr-print-header print-only">
                        <h2>Reporte Diario de Guías</h2>
                        <p>${startDate === endDate ? startDate : startDate + ' — ' + endDate}</p>
                        <p className="dr-print-meta">Generado: ${today} · ${groupLabel}</p>
                    </div>

                    ${groupedEntries.map(({ key, label, items }) => html`
                        <div className="dr-group" key=${key}>
                            ${groupBy !== 'none' ? html`
                                <h4 className="dr-group-title">
                                    ${label}
                                    <span className="dr-group-count">(${items.length})</span>
                                </h4>
                            ` : null}
                            <table className="dr-table">
                                <thead>
                                    <tr>
                                        <th>#</th>
                                        <th>Guía</th>
                                        ${activeCols.map((c) => html`<th key=${c.key}>${c.label}</th>`)}
                                    </tr>
                                </thead>
                                <tbody>
                                    ${items.map((entry, idx) => html`
                                        <tr key=${entry.id}>
                                            <td>${idx + 1}</td>
                                            <td className="dr-waybill-cell">${entry.waybill_no}</td>
                                            ${activeCols.map((c) => html`
                                                <td key=${c.key} className=${c.key === 'address' ? 'dr-address-cell' : ''}>
                                                    ${c.getValue(entry)}
                                                </td>
                                            `)}
                                        </tr>
                                    `)}
                                </tbody>
                            </table>
                        </div>
                    `)}

                    <div className="dr-print-footer print-only">
                        <p>Total guías: ${total}</p>
                    </div>
                </div>
            </div>
        </div>
    `;
}

export default function FloatingDailyReport() {
    const [panelOpen, setPanelOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [editData, setEditData] = useState({});
    const [savingId, setSavingId] = useState(null);
    const {
        startDate, setStartDate,
        endDate, setEndDate,
        groupBy, setGroupBy,
        groupedEntries,
        totalEntries,
        loading, error,
        loadEntries,
        handleDelete,
        handleUpdateEntry,
        inputValue, setInputValue,
        reportDate, setReportDate,
        ingesting,
        ingestResult,
        handleIngest,
        previewOpen, setPreviewOpen,
    } = useDailyReport();

    const startEdit = (entry) => {
        setEditingId(entry.id);
        setEditData({
            notes: entry.notes || '',
            status: entry.status || '',
        });
    };

    const cancelEdit = () => {
        setEditingId(null);
        setEditData({});
    };

    const saveEdit = async (entryId) => {
        setSavingId(entryId);
        try {
            await handleUpdateEntry(entryId, editData);
            setEditingId(null);
            setEditData({});
        } catch (e) {
            console.error('Error saving:', e);
        } finally {
            setSavingId(null);
        }
    };

    return html`
        <div className="floating-daily-report-wrapper no-print">
            <button
                type="button"
                className="floating-daily-report-btn"
                title="Reporte diario de guías"
                onClick=${() => setPanelOpen(true)}
            >
                📋
            </button>

            ${panelOpen ? html`
                <div className="dr-overlay" onClick=${() => setPanelOpen(false)}>
                    <div className="dr-panel" onClick=${(e) => e.stopPropagation()}>
                        <header className="dr-panel-header">
                            <div className="dr-panel-title">
                                <span className="dr-panel-icon">📋</span>
                                <h3>Reporte Diario de Guías</h3>
                            </div>
                            <button type="button" className="dr-close-btn" onClick=${() => setPanelOpen(false)}>✕</button>
                        </header>

                        <section className="dr-section">
                            <h4 className="dr-section-title">➕ Agregar guías</h4>
                            <div className="dr-ingest-row">
                                <label className="dr-label">Fecha del reporte</label>
                                <input
                                    type="date"
                                    className="dr-date-input"
                                    value=${reportDate}
                                    onChange=${(e) => setReportDate(e.target.value)}
                                />
                            </div>
                            <textarea
                                className="dr-textarea"
                                placeholder="Pega los números de guía (uno por línea)"
                                value=${inputValue}
                                onInput=${(e) => setInputValue(e.target.value)}
                                rows="5"
                            ></textarea>
                            <button
                                type="button"
                                className="dr-ingest-btn"
                                onClick=${handleIngest}
                                disabled=${ingesting}
                            >
                                ${ingesting ? '⏳ Procesando…' : '🔄 Consultar y guardar'}
                            </button>
                            ${ingestResult ? html`
                                <p className="dr-ingest-result">
                                    ✅ ${ingestResult.saved} guardadas
                                    ${(ingestResult.errors && ingestResult.errors.length) ? html` · ⚠️ ${ingestResult.errors.length} con error` : null}
                                </p>
                            ` : null}
                        </section>

                        <hr className="dr-divider" />

                        <section className="dr-section">
                            <h4 className="dr-section-title">🔍 Filtrar y consultar</h4>
                            <div className="dr-filter-row">
                                <div className="dr-filter-group">
                                    <label className="dr-label">Desde</label>
                                    <input type="date" className="dr-date-input"
                                        value=${startDate}
                                        onChange=${(e) => setStartDate(e.target.value)} />
                                </div>
                                <div className="dr-filter-group">
                                    <label className="dr-label">Hasta</label>
                                    <input type="date" className="dr-date-input"
                                        value=${endDate}
                                        onChange=${(e) => setEndDate(e.target.value)} />
                                </div>
                                <div className="dr-filter-group">
                                    <label className="dr-label">Agrupar</label>
                                    <select className="dr-select"
                                        value=${groupBy}
                                        onChange=${(e) => setGroupBy(e.target.value)}>
                                        <option value="none">Sin agrupar</option>
                                        <option value="messenger">Por mensajero</option>
                                        <option value="city">Por ciudad</option>
                                    </select>
                                </div>
                            </div>
                            <button
                                type="button"
                                className="dr-load-btn"
                                onClick=${loadEntries}
                                disabled=${loading}
                            >
                                ${loading ? '⏳ Cargando…' : '📥 Cargar entradas'}
                            </button>
                        </section>

                        ${error ? html`<p className="dr-error">${error}</p>` : null}

                        ${totalEntries > 0 ? html`
                            <section className="dr-section">
                                <div className="dr-entries-header">
                                    <h4 className="dr-section-title">
                                        📄 ${totalEntries} entrada${totalEntries !== 1 ? 's' : ''}
                                    </h4>
                                    <button
                                        type="button"
                                        className="dr-preview-open-btn"
                                        onClick=${() => setPreviewOpen(true)}
                                    >
                                        👁️ Vista previa / PDF
                                    </button>
                                </div>
                                <div className="dr-entries-list">
                                    ${groupedEntries.map(({ key, label, items }) => html`
                                        <div className="dr-entry-group" key=${key}>
                                            ${groupBy !== 'none' ? html`
                                                <div className="dr-entry-group-label">${label} (${items.length})</div>
                                            ` : null}
                                            ${items.map((entry) => {
                                                const isDelivered = (entry.status || '').toLowerCase().includes('firm');
                                                const isEditing = editingId === entry.id;
                                                const editStatus = editData.status !== undefined ? editData.status : entry.status || '';
                                                const editNotes = editData.notes !== undefined ? editData.notes : entry.notes || '';
                                                
                                                return html`
                                                    <div className="dr-entry-card ${isEditing ? 'editing' : ''}" key=${entry.id}>
                                                        <div className="dr-entry-main">
                                                            <span className="dr-entry-waybill">${entry.waybill_no}</span>
                                                            <span className="dr-entry-city">${entry.city || '—'}</span>
                                                        </div>
                                                        <div className="dr-entry-sub">
                                                            <span>${entry.messenger_name || 'Sin mensajero'}</span>
                                                            <span className=${'dr-status-badge ' + (isDelivered ? 'delivered' : 'pending')}>
                                                                ${entry.status || '—'}
                                                            </span>
                                                        </div>
                                                        ${entry.address ? html`
                                                            <div className="dr-entry-address" title=${entry.address}>
                                                                📍 ${entry.address}
                                                            </div>
                                                        ` : null}
                                                        <div className="dr-entry-actions">
                                                            <button
                                                                type="button"
                                                                className="dr-edit-btn"
                                                                title="Editar notas y estado"
                                                                onClick=${() => isEditing ? cancelEdit() : startEdit(entry)}
                                                            >${isEditing ? '✕' : '✏️'}</button>
                                                            <button
                                                                type="button"
                                                                className="dr-delete-btn"
                                                                title="Eliminar entrada"
                                                                onClick=${() => handleDelete(entry.id)}
                                                            >✕</button>
                                                        </div>

                                                        ${isEditing ? html`
                                                            <div className="dr-entry-edit-panel">
                                                                <div className="dr-edit-group">
                                                                    <label className="dr-edit-label">Estado</label>
                                                                    <select 
                                                                        className="dr-edit-input"
                                                                        value=${editStatus}
                                                                        onChange=${(e) => setEditData(prev => ({ ...prev, status: e.target.value }))}
                                                                    >
                                                                        <option value="">— Sin especificar —</option>
                                                                        <option value="Resuelto">✅ Resuelto</option>
                                                                        <option value="No resuelto">❌ No resuelto</option>
                                                                    </select>
                                                                </div>
                                                                <div className="dr-edit-group">
                                                                    <label className="dr-edit-label">Notas</label>
                                                                    <textarea 
                                                                        className="dr-edit-textarea"
                                                                        value=${editNotes}
                                                                        onChange=${(e) => setEditData(prev => ({ ...prev, notes: e.target.value }))}
                                                                        placeholder="Agrega notas sobre esta guía..."
                                                                        rows="2"
                                                                    ></textarea>
                                                                </div>
                                                                <div className="dr-edit-actions">
                                                                    <button 
                                                                        type="button"
                                                                        className="dr-save-btn"
                                                                        onClick=${() => saveEdit(entry.id)}
                                                                        disabled=${savingId === entry.id}
                                                                    >
                                                                        ${savingId === entry.id ? '💾 Guardando...' : '💾 Guardar'}
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        className="dr-cancel-btn"
                                                                        onClick=${cancelEdit}
                                                                    >
                                                                        Cancelar
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        ` : null}
                                                    </div>
                                                `;
                                            })}
                                        </div>
                                    `)}
                                </div>
                            </section>
                        ` : null}
                    </div>
                </div>
            ` : null}

            ${previewOpen ? html`
                <${PrintPreviewModal}
                    groupedEntries=${groupedEntries}
                    startDate=${startDate}
                    endDate=${endDate}
                    groupBy=${groupBy}
                    onClose=${() => setPreviewOpen(false)}
                />
            ` : null}
        </div>
    `;
}
