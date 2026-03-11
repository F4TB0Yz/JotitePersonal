import { useState, useCallback, useMemo } from '../lib/ui.js';
import { toISODateInput } from '../utils/formatters.js';
import { fetchDailyReport } from '../services/messengerService.js';

export function useMessengerReport() {
    const today = toISODateInput(new Date());
    const [date, setDate] = useState(today);
    const [records, setRecords] = useState([]);
    const [selectedCodes, setSelectedCodes] = useState(new Set());
    const [filterText, setFilterText] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const loadDay = useCallback(async () => {
        if (!date) return;
        setLoading(true);
        setError('');
        try {
            const data = await fetchDailyReport(date);
            const recs = data.records || [];
            setRecords(recs);
            setSelectedCodes(new Set(recs.map((r) => r.dispatchStaffCode)));
        } catch (e) {
            setError(e.message || 'Error cargando datos.');
            setRecords([]);
        } finally {
            setLoading(false);
        }
    }, [date]);

    const toggleMessenger = useCallback((code) => {
        setSelectedCodes((prev) => {
            const next = new Set(prev);
            if (next.has(code)) next.delete(code);
            else next.add(code);
            return next;
        });
    }, []);

    const selectAll = useCallback(() => {
        setSelectedCodes(new Set(records.map((r) => r.dispatchStaffCode)));
    }, [records]);

    const deselectAll = useCallback(() => {
        setSelectedCodes(new Set());
    }, []);

    const filteredRecords = useMemo(() => {
        if (!filterText.trim()) return records;
        const q = filterText.trim().toLowerCase();
        return records.filter(
            (r) =>
                (r.dispatchStaffName || '').toLowerCase().includes(q) ||
                (r.dispatchStaffCode || '').toLowerCase().includes(q)
        );
    }, [records, filterText]);

    const selectedRecords = useMemo(
        () => records.filter((r) => selectedCodes.has(r.dispatchStaffCode)),
        [records, selectedCodes]
    );

    const totals = useMemo(() => {
        const t = { dispatchTotal: 0, signTotal: 0, nosignTotal: 0 };
        selectedRecords.forEach((r) => {
            t.dispatchTotal += r.dispatchTotal || 0;
            t.signTotal += r.signTotal || 0;
            t.nosignTotal += r.nosignTotal || 0;
        });
        t.effectiveness = t.dispatchTotal
            ? `${((t.signTotal / t.dispatchTotal) * 100).toFixed(1)}%`
            : '0%';
        return t;
    }, [selectedRecords]);

    const exportCSV = useCallback(() => {
        if (!selectedRecords.length) return;
        const header = 'Mensajero,Código,Asignados,Entregados,Pendientes,Efectividad';
        const rows = selectedRecords.map((r) =>
            [
                `"${(r.dispatchStaffName || '').replace(/"/g, '""')}"`,
                r.dispatchStaffCode,
                r.dispatchTotal,
                r.signTotal,
                r.nosignTotal,
                r.signTotalRate || '0%',
            ].join(',')
        );
        rows.push(
            ['"TOTAL"', '""', totals.dispatchTotal, totals.signTotal, totals.nosignTotal, totals.effectiveness].join(',')
        );
        const csv = [header, ...rows].join('\n');
        const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `informe_mensajeros_${date}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }, [selectedRecords, totals, date]);

    return {
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
    };
}

    const [selectedMessengers, setSelectedMessengers] = useState([]);
    const [reportDateFrom, setReportDateFrom] = useState(today);
    const [reportDateTo, setReportDateTo] = useState(today);
    const [reportData, setReportData] = useState([]);
    const [reportLoading, setReportLoading] = useState(false);
    const [reportError, setReportError] = useState('');

    useEffect(() => {
        if (!searchTerm || searchTerm.trim().length < 2) {
            setSearchResults([]);
            setDropdownOpen(false);
            return;
        }
        const handler = setTimeout(() => {
            searchMessengers(searchTerm)
                .then((data) => {
                    const codes = new Set(selectedMessengers.map((m) => m.accountCode));
                    const filtered = (data || []).filter((m) => !codes.has(m.accountCode));
                    setSearchResults(filtered);
                    setDropdownOpen(filtered.length > 0);
                })
                .catch(() => {
                    setSearchResults([]);
                    setDropdownOpen(false);
                });
        }, 300);
        return () => clearTimeout(handler);
    }, [searchTerm, selectedMessengers]);

    const addMessenger = useCallback((messenger) => {
        setSelectedMessengers((prev) => {
            if (prev.length >= MAX_MESSENGERS) return prev;
            if (prev.some((m) => m.accountCode === messenger.accountCode)) return prev;
            return [...prev, messenger];
        });
        setSearchTerm('');
        setDropdownOpen(false);
        setSearchResults([]);
    }, []);

    const removeMessenger = useCallback((accountCode) => {
        setSelectedMessengers((prev) => prev.filter((m) => m.accountCode !== accountCode));
    }, []);

    const clearMessengers = useCallback(() => {
        setSelectedMessengers([]);
        setReportData([]);
        setReportError('');
    }, []);

    const generateReport = useCallback(async () => {
        if (!selectedMessengers.length) return;
        const { start, end } = buildDateRange(reportDateFrom, reportDateTo);
        if (!start || !end) {
            setReportError('Rango de fechas inválido.');
            return;
        }
        setReportLoading(true);
        setReportError('');
        try {
            const payload = selectedMessengers.map((m) => ({
                accountCode: m.accountCode,
                networkCode: m.customerNetworkCode || m.orgCode || m.dispatchNetworkCode || m.siteCode || '',
                accountName: m.accountName
            }));
            const response = await fetchBulkMetrics(payload, start, end);
            setReportData(response.results || []);
        } catch (error) {
            setReportError(error.message || 'Error generando el informe.');
        } finally {
            setReportLoading(false);
        }
    }, [selectedMessengers, reportDateFrom, reportDateTo]);

    const totals = useMemo(() => {
        const t = { dispatchTotal: 0, signTotal: 0, nosignTotal: 0 };
        reportData.forEach((r) => {
            t.dispatchTotal += r.dispatchTotal || 0;
            t.signTotal += r.signTotal || 0;
            t.nosignTotal += r.nosignTotal || 0;
        });
        t.effectiveness = t.dispatchTotal
            ? `${(t.signTotal / t.dispatchTotal * 100).toFixed(1)}%`
            : '0%';
        return t;
    }, [reportData]);

    const exportCSV = useCallback(() => {
        if (!reportData.length) return;
        const header = 'Mensajero,Código,Asignados,Entregados,Pendientes,Efectividad';
        const rows = reportData.map((r) =>
            [
                `"${(r.accountName || '').replace(/"/g, '""')}"`,
                r.accountCode,
                r.dispatchTotal,
                r.signTotal,
                r.nosignTotal,
                r.effectiveness
            ].join(',')
        );
        const totalRow = [
            '"TOTAL"', '""',
            totals.dispatchTotal,
            totals.signTotal,
            totals.nosignTotal,
            totals.effectiveness
        ].join(',');
        rows.push(totalRow);
        const csv = [header, ...rows].join('\n');
        const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `informe_mensajeros_${reportDateFrom}_${reportDateTo}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }, [reportData, totals, reportDateFrom, reportDateTo]);

    return {
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
    };
}
