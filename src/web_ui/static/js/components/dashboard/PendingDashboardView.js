import { html, useState, useEffect } from '../../lib/ui.js';
import { usePendingDashboard } from '../../hooks/usePendingDashboard.js';
import { formatShortDate } from '../../utils/formatters.js';
import { fetchWaybillDetails, fetchWaybillPhones } from '../../services/addressService.js';
import { fetchMessengerContact } from '../../services/messengerService.js';
import DateRangePicker from '../shared/DateRangePicker.js';

function cellClass(value) {
    if (!value) return 'dash-cell-empty';
    if (value <= 5) return 'dash-cell-verylow';
    if (value <= 15) return 'dash-cell-low';
    if (value <= 30) return 'dash-cell-med';
    return 'dash-cell-high';
}

function resolveValue(options, fallback = '—') {
    for (const value of options) {
        if (value && value !== 'N/A') return value;
    }
    return fallback;
}

function getWaybillId(record, index) {
    return record.waybillNo || record.thirdWaybillNo || record.orderId || `registro-${index}`;
}

function getReceiverName(record) {
    return resolveValue([record.receiverName, record.receiver, record.receiverRealName, record.customerName], 'Sin destinatario');
}

function getReceiverCity(record) {
    return resolveValue([record.receiverCityName, record.receiverCity, record.receiverCitye, record.destCityName], 'Ciudad desconocida');
}

function getReceiverAddress(record) {
    return resolveValue([record.receiverAddress, record.receiverAddressDetail, record.receAddress, record.destAddress], 'Sin dirección registrada');
}

function getPackageStatus(record) {
    return resolveValue([record.statusName, record.status, record.waybillStatusName], 'Pendiente');
}

function pickFirstDate(record, fields, fallback = 'Sin Fecha') {
    for (const field of fields) {
        const value = record?.[field];
        if (value && value !== 'N/A') return value;
    }
    return fallback;
}

function getPackageDateByMode(record, dateMode, dateModes) {
    if (dateMode === dateModes.assignment) {
        return pickFirstDate(record, [
            'deliveryScanTimeLatest',
            'dispatchTime',
            'assignTime',
            'operateTime',
            'createTime',
            'updateTime',
            'scanTime'
        ]);
    }
    return pickFirstDate(record, [
        'destArrivalTime',
        'arrivalTime',
        'arriveTime',
        'inboundTime',
        'dispatchTime',
        'operateTime',
        'updateTime'
    ]);
}

function getSortTimestamp(value) {
    if (!value || value === 'Sin Fecha') return 0;
    const ts = new Date(value).getTime();
    return Number.isNaN(ts) ? 0 : ts;
}

function getPhoneButtonLabel(info) {
    if (!info) return '📞 Ver teléfono';
    if (info.loading) return 'Consultando…';
    if (info.value && info.visible) return 'Ocultar';
    return '📞 Ver teléfono';
}

const EXPORTABLE_FIELDS = [
    { key: 'waybillNo', label: 'Guía' },
    { key: 'receiverName', label: 'Destinatario' },
    { key: 'receiverCity', label: 'Ciudad' },
    { key: 'receiverAddress', label: 'Dirección' },
    { key: 'receiverPhone', label: 'Contacto' },
    { key: 'date', label: 'Fecha' },
    { key: 'status', label: 'Estado' },
    { key: 'staff', label: 'Mensajero' }
];

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
    const [showExportMenu, setShowExportMenu] = useState(false);
    const [exportFields, setExportFields] = useState(() => ({
        waybillNo: true,
        receiverName: true,
        receiverCity: true,
        receiverAddress: true,
        receiverPhone: false,
        date: true,
        status: true,
        staff: false
    }));

    useEffect(() => {
        if (loading) {
            setSelectedCell(null);
            setMessengerContacts({});
            setShowExportMenu(false);
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

    const toggleExportField = (key) => {
        setExportFields((prev) => ({
            ...prev,
            [key]: !prev[key]
        }));
    };

    const getExportCellValue = (pkg, detail, fieldKey) => {
        if (fieldKey === 'waybillNo') return pkg.waybillNo || 'N/A';
        if (fieldKey === 'receiverName') return detail?.receiverName || getReceiverName(pkg);
        if (fieldKey === 'receiverCity') return detail?.receiverCity || getReceiverCity(pkg);
        if (fieldKey === 'receiverAddress') return detail?.receiverAddress || getReceiverAddress(pkg);
        if (fieldKey === 'receiverPhone') return detail?.receiverPhone || 'N/A';
        if (fieldKey === 'date') return getPackageDateByMode(pkg, dateMode, dateModes);
        if (fieldKey === 'status') return detail?.status || getPackageStatus(pkg);
        if (fieldKey === 'staff') return selectedCell?.staff || 'N/A';
        return '';
    };

    const handleExportPdf = () => {
        if (!selectedCell || detailRows.length === 0) return;
        const activeFields = EXPORTABLE_FIELDS.filter((field) => exportFields[field.key]);
        if (!activeFields.length) {
            window.alert('Selecciona al menos un campo para exportar.');
            return;
        }

        const title = `Pendientes - ${selectedCell.staff}`;
        const periodLabel = selectedCell.day === 'ALL'
            ? 'Todos los días'
            : selectedCell.day === 'Sin Fecha'
                ? 'Sin fecha registrada'
                : formatShortDate(selectedCell.day);

        const tableHead = activeFields.map((field) => `<th>${field.label}</th>`).join('');
        const tableRows = detailRows.map((pkg) => {
            const detail = pkg.waybillNo ? detailMap[pkg.waybillNo] : null;
            const cells = activeFields
                .map((field) => `<td>${String(getExportCellValue(pkg, detail, field.key) || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</td>`)
                .join('');
            return `<tr>${cells}</tr>`;
        }).join('');

        const htmlContent = `
            <html>
                <head>
                    <meta charset="utf-8" />
                    <title>${title}</title>
                    <style>
                        body { font-family: Arial, sans-serif; color: #111; margin: 24px; }
                        h1 { font-size: 20px; margin: 0 0 6px; }
                        p { margin: 0 0 6px; font-size: 12px; }
                        table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 11px; }
                        th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }
                        th { background: #f2f2f2; }
                        @media print { body { margin: 12mm; } }
                    </style>
                </head>
                <body>
                    <h1>${title}</h1>
                    <p><strong>Fecha filtro:</strong> ${activeDateLabel} - ${periodLabel}</p>
                    <p><strong>Total paquetes:</strong> ${detailRows.length}</p>
                    <table>
                        <thead><tr>${tableHead}</tr></thead>
                        <tbody>${tableRows}</tbody>
                    </table>
                </body>
            </html>
        `;

        const printWindow = window.open('', '_blank', 'noopener,noreferrer,width=1200,height=900');
        if (!printWindow) {
            window.alert('No se pudo abrir la ventana para exportar PDF.');
            return;
        }

        printWindow.document.open();
        printWindow.document.write(htmlContent);
        printWindow.document.close();
        printWindow.focus();
        setTimeout(() => {
            printWindow.print();
        }, 300);
    };

    const detailRows = selectedCell
        ? [...selectedCell.records].sort((a, b) => {
            const bValue = getPackageDateByMode(b, dateMode, dateModes);
            const aValue = getPackageDateByMode(a, dateMode, dateModes);
            return getSortTimestamp(bValue) - getSortTimestamp(aValue);
        })
        : [];

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
                ${selectedCell
                    ? html`<section className="dash-detail-panel">
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
                                        Opciones PDF
                                    </button>
                                    ${showExportMenu
                                        ? html`<div className="dash-export-menu">
                                            <p className="dash-export-title">Campos a incluir</p>
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
                                            <button
                                                type="button"
                                                className="primary-btn dash-export-run-btn"
                                                onClick=${handleExportPdf}
                                            >
                                                Exportar PDF
                                            </button>
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
                    </section>`
                    : null}
            </div>
        </main>
    `;
}
