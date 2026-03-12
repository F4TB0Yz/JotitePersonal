import { useCallback, useState } from '../lib/ui.js';
import { toISODateInput } from '../utils/formatters.js';
import {
    fetchReturnApplications,
    fetchReturnPrintable,
    fetchReturnPrintUrl,
    syncReturnSnapshots,
} from '../services/returnsService.js';

function daysAgoISO(days) {
    const now = new Date();
    now.setDate(now.getDate() - days);
    return toISODateInput(now);
}

export function useReturns() {
    const [status, setStatus] = useState(1);
    const [printableFlag, setPrintableFlag] = useState(0);
    const [startDate, setStartDate] = useState(daysAgoISO(2));
    const [endDate, setEndDate] = useState(toISODateInput(new Date()));
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(20);
    const [records, setRecords] = useState([]);
    const [total, setTotal] = useState(0);
    const [pages, setPages] = useState(0);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState('');
    const [syncedAt, setSyncedAt] = useState('');
    const [snapshotsInserted, setSnapshotsInserted] = useState(0);
    const [printLinkLoadingWaybill, setPrintLinkLoadingWaybill] = useState('');
    const [printLinkMessage, setPrintLinkMessage] = useState('');

    const fetchReturns = useCallback(async ({ page = currentPage, persist = true } = {}) => {
        setLoading(true);
        setError('');
        setPrintLinkMessage('');
        try {
            const response = status === 'printable'
                ? await fetchReturnPrintable({
                    dateFrom: startDate,
                    dateTo: endDate,
                    current: page,
                    size: pageSize,
                    pringFlag: printableFlag,
                })
                : await fetchReturnApplications({
                    status,
                    dateFrom: startDate,
                    dateTo: endDate,
                    current: page,
                    size: pageSize,
                    saveSnapshot: persist,
                });

            const data = response?.data || {};
            setRecords(data.records || []);
            setTotal(Number(data.total || 0));
            setPages(Number(data.pages || 0));
            setCurrentPage(Number(data.current || page));
            setSyncedAt(data.synced_at || '');
            setSnapshotsInserted(Number(data.snapshots_inserted || 0));
        } catch (err) {
            setError(err.message || 'No se pudo consultar devoluciones');
        } finally {
            setLoading(false);
        }
    }, [status, startDate, endDate, pageSize, currentPage, printableFlag]);

    const runSync = useCallback(async () => {
        if (status === 'printable') {
            setError('La sincronización no aplica para la vista de impresión. Usa Buscar para refrescar.');
            return;
        }

        setSyncing(true);
        setError('');
        try {
            await syncReturnSnapshots({
                date_from: startDate,
                date_to: endDate,
                statuses: [Number(status)],
                size: pageSize,
                max_pages: 20,
            });
            await fetchReturns({ page: 1, persist: false });
        } catch (err) {
            setError(err.message || 'No se pudo sincronizar devoluciones');
        } finally {
            setSyncing(false);
        }
    }, [status, startDate, endDate, pageSize, fetchReturns]);

    const requestPrintUrl = useCallback(async (rowOrWaybill) => {
        const source = typeof rowOrWaybill === 'string' ? { waybill_no: rowOrWaybill } : (rowOrWaybill || {});
        const target = (source.waybill_no || source.waybillNo || '').trim().toUpperCase();
        if (!target) {
            setError('Waybill inválido para impresión');
            return null;
        }

        setPrintLinkLoadingWaybill(target);
        setError('');
        setPrintLinkMessage('');

        try {
            const response = await fetchReturnPrintUrl({
                waybillNo: target,
                printFlag: source.print_flag,
                printCount: source.print_count,
            });
            const data = response?.data || {};
            const printUrl = data.print_url || data.url || null;

            if (!printUrl) {
                setPrintLinkMessage(`No se recibió URL de impresión para ${target}.`);
                return null;
            }

            setPrintLinkMessage(`Link de impresión generado para ${target}.`);
            return printUrl;
        } catch (err) {
            setError(err.message || 'No se pudo obtener el link de impresión');
            return null;
        } finally {
            setPrintLinkLoadingWaybill('');
        }
    }, []);

    return {
        status,
        setStatus,
        printableFlag,
        setPrintableFlag,
        startDate,
        setStartDate,
        endDate,
        setEndDate,
        currentPage,
        setCurrentPage,
        pageSize,
        setPageSize,
        records,
        total,
        pages,
        loading,
        syncing,
        error,
        syncedAt,
        snapshotsInserted,
        printLinkLoadingWaybill,
        printLinkMessage,
        fetchReturns,
        runSync,
        requestPrintUrl,
    };
}
