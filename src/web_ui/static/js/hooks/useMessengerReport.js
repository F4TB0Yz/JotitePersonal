import { useState, useCallback, useMemo } from '../lib/ui.js';
import { toISODateInput } from '../utils/formatters.js';
import { fetchDailyReport } from '../services/messengerService.js';

export function useMessengerReport() {
    const today = toISODateInput(new Date());
    const [startDate, setStartDate] = useState(today);
    const [endDate, setEndDate] = useState(today);
    const [records, setRecords] = useState([]);
    const [selectedCodes, setSelectedCodes] = useState(new Set());
    const [filterText, setFilterText] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const loadDay = useCallback(async () => {
        if (!startDate || !endDate) return;
        setLoading(true);
        setError('');
        try {
            const data = await fetchDailyReport(startDate, endDate);
            const recs = data.records || [];
            setRecords(recs);
            setSelectedCodes(new Set(recs.map((r) => r.dispatchStaffCode)));
        } catch (e) {
            setError(e.message || 'Error cargando datos.');
            setRecords([]);
        } finally {
            setLoading(false);
        }
    }, [startDate, endDate]);

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
        a.download = `informe_mensajeros_${startDate}_al_${endDate}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }, [selectedRecords, totals, startDate, endDate]);

    return {
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
    };
}

