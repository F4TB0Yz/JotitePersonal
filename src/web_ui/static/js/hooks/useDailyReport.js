import { useState, useCallback, useMemo } from '../lib/ui.js';
import { toISODateInput } from '../utils/formatters.js';
import {
    fetchDailyReportEntries,
    ingestDailyReportEntries,
    deleteDailyReportEntry,
    updateDailyReportEntry,
} from '../services/dailyReportService.js';

export function useDailyReport() {
    const today = toISODateInput(new Date());

    // --- filter state ---
    const [startDate, setStartDate] = useState(today);
    const [endDate, setEndDate] = useState(today);
    const [groupBy, setGroupBy] = useState('none'); // 'none' | 'messenger' | 'city'

    // --- entries ---
    const [entries, setEntries] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // --- ingest panel state ---
    const [inputValue, setInputValue] = useState('');
    const [reportDate, setReportDate] = useState(today);
    const [ingesting, setIngesting] = useState(false);
    const [ingestResult, setIngestResult] = useState(null); // { saved, errors }

    // --- preview modal ---
    const [previewOpen, setPreviewOpen] = useState(false);

    // -------------------------------------------------------
    // Load entries from API
    // -------------------------------------------------------
    const loadEntries = useCallback(async () => {
        if (!startDate || !endDate) return;
        setLoading(true);
        setError('');
        try {
            const data = await fetchDailyReportEntries(startDate, endDate);
            setEntries(Array.isArray(data) ? data : []);
        } catch (e) {
            setError(e.message || 'Error cargando entradas.');
            setEntries([]);
        } finally {
            setLoading(false);
        }
    }, [startDate, endDate]);

    // -------------------------------------------------------
    // Ingest new waybills
    // -------------------------------------------------------
    const handleIngest = useCallback(async () => {
        const waybillNos = inputValue
            .split(/[\n,\s]+/)
            .map((w) => w.trim().toUpperCase())
            .filter(Boolean);

        if (!waybillNos.length) {
            setError('Ingresa al menos una guía.');
            return;
        }
        if (!reportDate) {
            setError('Selecciona una fecha para el reporte.');
            return;
        }

        setIngesting(true);
        setError('');
        setIngestResult(null);
        try {
            const result = await ingestDailyReportEntries(waybillNos, reportDate);
            setIngestResult(result);
            setInputValue('');
            // Reload entries to show new ones
            await loadEntries();
        } catch (e) {
            setError(e.message || 'Error al procesar las guías.');
        } finally {
            setIngesting(false);
        }
    }, [inputValue, reportDate, loadEntries]);

    // -------------------------------------------------------
    // Delete a single entry
    // -------------------------------------------------------
    const handleDelete = useCallback(async (id) => {
        try {
            await deleteDailyReportEntry(id);
            setEntries((prev) => prev.filter((e) => e.id !== id));
        } catch (e) {
            setError(e.message || 'Error al eliminar la entrada.');
        }
    }, []);

    // -------------------------------------------------------
    // Update notes and/or status of an entry
    // -------------------------------------------------------
    const handleUpdateEntry = useCallback(async (id, updates) => {
        try {
            const result = await updateDailyReportEntry(id, updates);
            // Update the entry in the local state
            setEntries((prev) => prev.map((e) => 
                e.id === id ? { ...e, ...result } : e
            ));
            return result;
        } catch (e) {
            setError(e.message || 'Error al actualizar la entrada.');
            throw e;
        }
    }, []);

    // -------------------------------------------------------
    // Grouped / sorted derived data
    // -------------------------------------------------------
    const groupedEntries = useMemo(() => {
        if (groupBy === 'none') {
            return [{ key: 'all', label: 'Todas las guías', items: entries }];
        }

        const field = groupBy === 'messenger' ? 'messenger_name' : 'city';
        const map = new Map();
        for (const entry of entries) {
            const key = entry[field] || 'Sin asignar';
            if (!map.has(key)) map.set(key, []);
            map.get(key).push(entry);
        }
        return Array.from(map.entries())
            .sort(([a], [b]) => a.localeCompare(b, 'es'))
            .map(([key, items]) => ({ key, label: key, items }));
    }, [entries, groupBy]);

    const totalEntries = entries.length;

    return {
        // filter
        startDate, setStartDate,
        endDate, setEndDate,
        groupBy, setGroupBy,
        // entries
        entries,
        groupedEntries,
        totalEntries,
        loading,
        error,
        loadEntries,
        handleDelete,
        handleUpdateEntry,
        // ingest
        inputValue, setInputValue,
        reportDate, setReportDate,
        ingesting,
        ingestResult,
        handleIngest,
        // preview
        previewOpen, setPreviewOpen,
    };
}
