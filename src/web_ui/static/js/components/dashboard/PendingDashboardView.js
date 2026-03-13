import { html, useState, useEffect } from '../../lib/ui.js';
import { usePendingDashboard } from '../../hooks/usePendingDashboard.js';
import usePendingExports from '../../hooks/usePendingExports.js';
import { formatShortDate } from '../../utils/formatters.js';
import { fetchWaybillDetails, fetchWaybillPhones } from '../../services/addressService.js';
import { fetchMessengerContact } from '../../services/messengerService.js';
import DateRangePicker from '../shared/DateRangePicker.js';
import PendingDetailPanel from './PendingDetailPanel.js';

import { cellClass, getPackageDateByMode, getSortTimestamp } from '../../utils/pendingHelpers.js';


export default function PendingDashboardView() {
    const {
        dateMode,
        setDateMode,
        dateModes,
        selectedStaff,
        setSelectedStaff,
        staffOptions,
        networkCode,
        setNetworkCode,
        startDate,
        setStartDate,
        endDate,
        setEndDate,
        fetchDashboard,
        loading,
        error,
        subtitle,
        summary,
        filteredRecords,
        tableData,
        getRecordsByCell,
        getRecordsByStaff,
        getSampleWaybillForStaff
    } = usePendingDashboard();

    const assignmentModeActive = dateMode === dateModes.assignment;
    const activeDateLabel = assignmentModeActive ? 'Asignación mensajero' : 'Arribo destino';

    const [selectedCell, setSelectedCell] = useState(null);
    const [detailMap, setDetailMap] = useState({});
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState('');
    const [phoneState, setPhoneState] = useState({});
    const [messengerContacts, setMessengerContacts] = useState({});

    const detailRows = selectedCell
        ? [...selectedCell.records].sort((a, b) => {
            const bValue = getPackageDateByMode(b, dateMode, dateModes);
            const aValue = getPackageDateByMode(a, dateMode, dateModes);
            return getSortTimestamp(bValue) - getSortTimestamp(aValue);
        })
        : [];

    const {
        showExportMenu,
        setShowExportMenu,
        exportJsonLoading,
        exportJsonError,
        exportFields,
        toggleExportField,
        handleExportPdf,
        handleExportDashboardJson,
        handleExportJson
    } = usePendingExports({
        detailMap,
        dateMode,
        dateModes,
        networkCode,
        startDate,
        endDate,
        selectedStaff,
        activeDateLabel,
        filteredRecords,
        detailRows,
        selectedCell
    });

    useEffect(() => {
        if (loading) {
            setSelectedCell(null);
            setMessengerContacts({});
            setShowExportMenu(false);
            setExportJsonError('');
        }
    }, [loading]);

    useEffect(() => {
        setMessengerContacts({});
    }, [networkCode]);

    useEffect(() => {
        if (!selectedCell) {
            setDetailMap({});
            setDetailError('');
            setDetailLoading(false);
            setPhoneState({});
            setExportJsonError('');
            return;
        }
        const ids = Array.from(
            new Set(
                selectedCell.records
                    .map((item) => item.waybillNo)
                    .filter((wb) => typeof wb === 'string' && wb.trim().length > 0)
            )
        );
        if (ids.length === 0) {
            setDetailMap({});
            setDetailError('');
            setDetailLoading(false);
            return;
        }
        let cancelled = false;
        setDetailLoading(true);
        setDetailError('');
        fetchWaybillDetails(ids)
            .then((data) => {
                if (cancelled) return;
                setDetailMap(data || {});
            })
            .catch((err) => {
                if (cancelled) return;
                setDetailError(err?.message || 'No se pudo obtener el detalle de las guías.');
                setDetailMap({});
            })
            .finally(() => {
                if (cancelled) return;
                setDetailLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [selectedCell]);

    useEffect(() => {
        if (!selectedCell) return;
        const allowed = new Set(
            selectedCell.records
                .map((item) => item.waybillNo)
                .filter((wb) => typeof wb === 'string' && wb.trim().length > 0)
        );
        setPhoneState((prev) => {
            const next = {};
            allowed.forEach((wb) => {
                if (prev[wb]) {
                    next[wb] = prev[wb];
                }
            });
            return next;
        });
    }, [selectedCell]);

    const handleCellClick = (staff, day) => {
        const records = getRecordsByCell(staff, day);
        if (!records.length) {
            setSelectedCell(null);
            return;
        }
        setSelectedCell({
            staff,
            day,
            records
        });
    };

    const handleTotalClick = (staff) => {
        const records = getRecordsByStaff(staff);
        if (!records.length) {
            setSelectedCell(null);
            return;
        }
        setSelectedCell({
            staff,
            day: 'ALL',
            records
        });
    };

    const handleMessengerClick = (staff) => {
        if (!staff || staff === 'Sin enrutar') return;
        const key = staff.trim().toLowerCase();
        const current = messengerContacts[key];
        if (current?.value && !current.loading) {
            setMessengerContacts((prev) => ({
                ...prev,
                [key]: {
                    ...current,
                    visible: !current.visible
                }
            }));
            return;
        }

        setMessengerContacts((prev) => ({
            ...prev,
            [key]: {
                value: '',
                loading: true,
                visible: false,
                error: ''
            }
        }));

        const sampleWaybill = getSampleWaybillForStaff(staff);
        fetchMessengerContact(staff, networkCode, sampleWaybill)
            .then((data) => {
                const phone = data?.phone;
                setMessengerContacts((prev) => ({
                    ...prev,
                    [key]: {
                        value: phone || '',
                        loading: false,
                        visible: Boolean(phone),
                        error: phone ? '' : 'Teléfono no disponible'
                    }
                }));
            })
            .catch((err) => {
                setMessengerContacts((prev) => ({
                    ...prev,
                    [key]: {
                        value: '',
                        loading: false,
                        visible: false,
                        error: err?.message || 'Error consultando mensajero'
                    }
                }));
            });
    };

    const handleStaffFilterToggle = (staff) => {
        if (!staff) return;
        setSelectedCell(null);
        setSelectedStaff((prev) => (prev === staff ? 'ALL' : staff));
    };

    const handlePhoneClick = (waybillNo) => {
        if (!waybillNo) return;
        const current = phoneState[waybillNo];
        if (current?.value && !current.loading) {
            setPhoneState((prev) => ({
                ...prev,
                [waybillNo]: {
                    ...current,
                    visible: !current.visible
                }
            }));
            return;
        }

        setPhoneState((prev) => ({
            ...prev,
            [waybillNo]: {
                value: '',
                visible: true,
                loading: true,
                error: ''
            }
        }));

        fetchWaybillPhones([waybillNo])
            .then((data) => {
                const phone = data?.[waybillNo];
                setPhoneState((prev) => ({
                    ...prev,
                    [waybillNo]: {
                        value: phone || '',
                        visible: Boolean(phone),
                        loading: false,
                        error: phone ? '' : 'Teléfono no disponible'
                    }
                }));
            })
            .catch((err) => {
                setPhoneState((prev) => ({
                    ...prev,
                    [waybillNo]: {
                        value: '',
                        visible: false,
                        loading: false,
                        error: err?.message || 'Error consultando teléfono'
                    }
                }));
            });
    };


    return html`
        <main className="dashboard-main">
            <div className="dashboard-shell">
                <div className="dashboard-header">
                    <div>
                        <h2>Guías pendientes por mensajero</h2>
                        <p>${subtitle || 'Punto: -- | Periodo: -- a --'}</p>
                    </div>
                    <form className="dashboard-filters" onSubmit=${(event) => { event.preventDefault(); fetchDashboard(); }}>
                        <div className="dash-filters-row">
                        <label>
                            Código Red
                            <input type="text" value=${networkCode} onChange=${(e) => setNetworkCode(e.target.value)} />
                        </label>
                        <label>
                            Mensajero
                            <select value=${selectedStaff} onChange=${(e) => setSelectedStaff(e.target.value)}>
                                <option value="ALL">Todos</option>
                                ${staffOptions.map((staff) => html`<option key=${staff} value=${staff}>${staff}</option>`)}
                            </select>
                        </label>
                        </div>
                        <button
                            type="button"
                            className="dash-clear-filter-btn"
                            disabled=${selectedStaff === 'ALL'}
                            onClick=${() => setSelectedStaff('ALL')}
                        >
                            Limpiar filtro
                        </button>
                        <${DateRangePicker} 
                            label="Rango de Fechas"
                            dateFrom=${startDate} 
                            dateTo=${endDate} 
                            onDateChange=${(s, e) => {
                                setStartDate(s);
                                setEndDate(e);
                            }} 
                        />
                        <button
                            type="button"
                            className="dash-date-toggle-btn"
                            onClick=${() => setDateMode(assignmentModeActive ? dateModes.arrival : dateModes.assignment)}
                        >
                            Fecha: ${activeDateLabel}
                        </button>
                        <button type="submit" className="primary-btn" disabled=${loading}>
                            ${loading ? 'Cargando…' : 'Consultar API'}
                        </button>
                        <button
                            type="button"
                            className="dash-json-export-btn"
                            disabled=${loading || exportJsonLoading || filteredRecords.length === 0}
                            onClick=${handleExportDashboardJson}
                            title="Exportar todos los paquetes visibles en JSON para análisis con IA"
                        >
                            ${exportJsonLoading ? '⌛ JSON…' : '↓ JSON'}
                        </button>
                    </form>
                </div>
                <div className="dashboard-cards">
                    <div className="dashboard-card">
                        <span className="card-value">${summary.total}</span>
                        <span className="card-label">Total pendientes</span>
                    </div>
                    <div className="dashboard-card warning">
                        <span className="card-value">${summary.old}</span>
                        <span className="card-label">Antiguos (5+ días)</span>
                    </div>
                    <div className="dashboard-card muted">
                        <span className="card-value">${summary.unassigned}</span>
                        <span className="card-label">Sin enrutar</span>
                    </div>
                </div>
                <div className="dash-table-container">
                    ${error
                        ? html`<div className="dash-error">${error}</div>`
                        : tableData.rows.length === 0
                            ? html`<div className="dash-placeholder">No hay paquetes pendientes en este rango.</div>`
                            : html`<table className="dash-target-table">
                                <thead>
                                    <tr>
                                        <th>Empleado de entrega</th>
                                        ${tableData.dates.map((date) => html`<th key=${date}>${formatShortDate(date)}</th>`)}
                                        <th>Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${tableData.rows.map((row) => {
                                        const staffKey = row.staff ? row.staff.trim().toLowerCase() : '';
                                        const messengerInfo = staffKey ? messengerContacts[staffKey] : null;
                                        const isStaffSelected = selectedStaff === row.staff;
                                        return html`<tr key=${row.staff} className=${row.staff === 'Sin enrutar' ? 'dash-row-sin-enrutar' : ''}>
                                            <td className="dash-staff-cell">
                                                <div className="dash-staff-main">
                                                    <input
                                                        type="checkbox"
                                                        className="dash-staff-checkbox"
                                                        checked=${isStaffSelected}
                                                        onChange=${() => handleStaffFilterToggle(row.staff)}
                                                        title="Filtrar este mensajero"
                                                    />
                                                    <button
                                                        type="button"
                                                        className=${`dash-staff-filter-btn ${isStaffSelected ? 'is-active' : ''}`}
                                                        onClick=${() => handleStaffFilterToggle(row.staff)}
                                                        title="Filtrar este mensajero"
                                                    >
                                                        ${row.staff}
                                                    </button>
                                                    ${row.staff !== 'Sin enrutar'
                                                        ? html`<button
                                                        type="button"
                                                        className="dash-staff-btn"
                                                        onClick=${() => handleMessengerClick(row.staff)}
                                                        title="Ver contacto del mensajero"
                                                    >
                                                        <span className="dash-staff-icon">${messengerInfo?.loading ? '…' : '📱'}</span>
                                                    </button>`
                                                        : null}
                                                </div>
                                                ${messengerInfo
                                                    ? html`
                                                        ${messengerInfo.error ? html`<span className="dash-phone-error">${messengerInfo.error}</span>` : null}
                                                        ${messengerInfo.value && messengerInfo.visible ? html`<span className="dash-staff-phone">${messengerInfo.value}</span>` : null}
                                                    `
                                                    : null}
                                            </td>
                                            ${tableData.dates.map((date) => {
                                                const value = row.data[date] || 0;
                                                const clickable = value > 0;
                                                const classes = `${cellClass(value)} ${clickable ? 'dash-cell-clickable' : ''}`.trim();
                                                return html`<td
                                                    key=${`${row.staff}-${date}`}
                                                    className=${classes}
                                                    onClick=${clickable ? () => handleCellClick(row.staff, date) : undefined}
                                                    role=${clickable ? 'button' : undefined}
                                                    title=${clickable ? 'Ver paquetes del mensajero' : undefined}
                                                >
                                                    ${value || ''}
                                                </td>`;
                                            })}
                                            <td
                                                className=${`dash-total-cell ${row.data.total > 0 ? 'dash-cell-clickable' : ''}`}
                                                onClick=${row.data.total > 0 ? () => handleTotalClick(row.staff) : undefined}
                                                role=${row.data.total > 0 ? 'button' : undefined}
                                                title=${row.data.total > 0 ? 'Ver todos los paquetes del mensajero' : undefined}
                                            >
                                                ${row.data.total}
                                            </td>
                                        </tr>`;
                                    })}
                                </tbody>
                            </table>`}
                </div>
                <${PendingDetailPanel}
                    selectedCell=${selectedCell}
                    activeDateLabel=${activeDateLabel}
                    showExportMenu=${showExportMenu}
                    setShowExportMenu=${setShowExportMenu}
                    exportFields=${exportFields}
                    toggleExportField=${toggleExportField}
                    handleExportPdf=${handleExportPdf}
                    exportJsonLoading=${exportJsonLoading}
                    handleExportJson=${handleExportJson}
                    exportJsonError=${exportJsonError}
                    setSelectedCell=${setSelectedCell}
                    detailLoading=${detailLoading}
                    detailError=${detailError}
                    detailRows=${detailRows}
                    detailMap=${detailMap}
                    phoneState=${phoneState}
                    handlePhoneClick=${handlePhoneClick}
                    dateMode=${dateMode}
                    dateModes=${dateModes}
                />
            </div>
        </main>
    `;
}
