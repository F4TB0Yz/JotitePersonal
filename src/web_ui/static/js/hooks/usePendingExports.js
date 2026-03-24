import { useState } from '../lib/ui.js';
import { fetchWaybillIntelligenceExport } from '../services/addressService.js';
import {
    downloadJsonFile,
    safeFileNamePart,
    getReceiverName,
    getReceiverCity,
    getReceiverAddress,
    getPackageStatus,
    EXPORTABLE_FIELDS
} from '../utils/pendingHelpers.js';
import { formatShortDate } from '../utils/formatters.js';

export default function usePendingExports({
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
}) {
    const [showExportMenu, setShowExportMenu] = useState(false);
    const [exportJsonLoading, setExportJsonLoading] = useState(false);
    const [exportJsonError, setExportJsonError] = useState('');
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

    const toggleExportField = (key) => {
        setExportFields((prev) => ({
            ...prev,
            [key]: !prev[key]
        }));
    };

    const buildIntelligencePackages = (records, exportResults, staffLabelResolver) => records.map((pkg, index) => {
        const waybillNo = pkg.waybillNo || '';
        const detail = waybillNo ? (detailMap[waybillNo] || exportResults[waybillNo]?.detail || null) : null;
        const intelligence = waybillNo ? exportResults[waybillNo] : null;

        return {
            rowIndex: index + 1,
            waybillNo: waybillNo || null,
            visibleSnapshot: {
                receiverName: detail?.receiverName || getReceiverName(pkg),
                receiverCity: detail?.receiverCity || getReceiverCity(pkg),
                receiverAddress: detail?.receiverAddress || getReceiverAddress(pkg),
                receiverPhone: detail?.receiverPhone || null,
                status: detail?.status || getPackageStatus(pkg),
                staff: staffLabelResolver(pkg),
                referenceDate: pkg.date || 'Sin Fecha'
            },
            sourceRecord: pkg,
            officialDetail: intelligence?.detail || detail,
            rawOfficialData: intelligence?.raw || null,
            movements: intelligence?.timeline || [],
            movementSummary: intelligence?.timelineSummary || {
                eventCount: 0,
                lastEventTime: '',
                lastStatus: ''
            },
            errors: intelligence?.errors || []
        };
    });

    const getExportCellValue = (pkg, detail, fieldKey) => {
        if (fieldKey === 'waybillNo') return pkg.waybillNo || 'N/A';
        if (fieldKey === 'receiverName') return detail?.receiverName || getReceiverName(pkg);
        if (fieldKey === 'receiverCity') return detail?.receiverCity || getReceiverCity(pkg);
        if (fieldKey === 'receiverAddress') return detail?.receiverAddress || getReceiverAddress(pkg);
        if (fieldKey === 'receiverPhone') return detail?.receiverPhone || 'N/A';
        if (fieldKey === 'date') return pkg.date || 'Sin Fecha';
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

    const exportRecordsAsJson = async ({ records, fileLabel, scope, detailDay = null, detailDayLabel = null, staffLabelResolver }) => {
        if (!records || records.length === 0) return;

        const waybills = Array.from(
            new Set(
                records
                    .map((pkg) => pkg.waybillNo)
                    .filter((waybillNo) => typeof waybillNo === 'string' && waybillNo.trim().length > 0)
            )
        );

        if (waybills.length === 0) {
            window.alert('No hay guías válidas para exportar.');
            return;
        }

        setExportJsonLoading(true);
        setExportJsonError('');

        try {
            const exportResponse = await fetchWaybillIntelligenceExport(waybills);
            const exportResults = exportResponse?.results || {};
            const packages = buildIntelligencePackages(records, exportResults, staffLabelResolver);

            const payload = {
                exportedAt: new Date().toISOString(),
                generatedAt: exportResponse?.generatedAt || '',
                source: 'dashboard-pendientes',
                scope,
                filters: {
                    networkCode,
                    startDate,
                    endDate,
                    dateMode,
                    dateLabel: activeDateLabel,
                    selectedStaff,
                    detailDay,
                    detailDayLabel
                },
                summary: {
                    packageCount: packages.length,
                    waybillCount: waybills.length,
                    exportedMovementCount: packages.reduce(
                        (total, item) => total + (item.movements?.length || 0),
                        0
                    )
                },
                packages
            };

            const fileName = [
                'dashboard-pendientes',
                safeFileNamePart(networkCode, 'red'),
                safeFileNamePart(fileLabel, 'filtro')
            ].join('-') + '.json';

            downloadJsonFile(fileName, payload);
        } catch (err) {
            setExportJsonError(err?.message || 'No se pudo generar el JSON.');
        } finally {
            setExportJsonLoading(false);
        }
    };

    const handleExportDashboardJson = async () => {
        await exportRecordsAsJson({
            records: filteredRecords,
            fileLabel: selectedStaff === 'ALL' ? 'tabla-completa' : `tabla-${selectedStaff}`,
            scope: 'dashboard-table',
            detailDay: 'ALL',
            detailDayLabel: 'Todos los días visibles',
            staffLabelResolver: (pkg) => pkg.deliveryUser || 'Sin enrutar'
        });
    };

    const handleExportJson = async () => {
        if (!selectedCell || detailRows.length === 0) return;
        const selectedStaffLabel = selectedCell.staff || 'Sin enrutar';
        const periodLabel = selectedCell.day === 'ALL'
            ? 'Todos los días'
            : selectedCell.day === 'Sin Fecha'
                ? 'Sin fecha registrada'
                : formatShortDate(selectedCell.day);

        await exportRecordsAsJson({
            records: detailRows,
            fileLabel: `${selectedStaffLabel}-${selectedCell.day === 'ALL' ? 'todos' : selectedCell.day}`,
            scope: 'detail-panel',
            detailDay: selectedCell.day,
            detailDayLabel: periodLabel,
            staffLabelResolver: () => selectedStaffLabel
        });
    };

    return {
        showExportMenu,
        setShowExportMenu,
        exportJsonLoading,
        exportJsonError,
        exportFields,
        toggleExportField,
        handleExportPdf,
        handleExportDashboardJson,
        handleExportJson,
        setExportJsonError
    };
}
