import { useState, useEffect, useCallback, useMemo } from '../lib/ui.js';
import { toISODateInput, buildDateRange } from '../utils/formatters.js';
import { searchMessengers, fetchMessengerMetrics, fetchMessengerWaybills } from '../services/messengerService.js';
import { fetchAddressesForWaybills } from '../services/addressService.js';
import { deleteSettlement, fetchMessengerRate, fetchSettlements, generateSettlement, reprintWaybills, setMessengerRate } from '../services/settlementService.js';
import { STATUS_DICTIONARY } from '../utils/constants.js';

function groupWaybillsByDay(list) {
    return list.reduce((acc, item) => {
        const date = item.dispatchTime ? item.dispatchTime.split(' ')[0] : 'Desconocido';
        if (!acc[date]) acc[date] = { total: 0, delivered: 0, pending: 0 };
        acc[date].total += 1;
        if (item.isSign === 1) acc[date].delivered += 1;
        else acc[date].pending += 1;
        return acc;
    }, {});
}

function translateStatus(status) {
    return STATUS_DICTIONARY[status] || status || 'N/A';
}

export function useMessengerAdmin() {
    const today = toISODateInput(new Date());
    const [searchTerm, setSearchTerm] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const [selectedMessenger, setSelectedMessenger] = useState(null);
    const [dateFrom, setDateFrom] = useState(today);
    const [dateTo, setDateTo] = useState(today);
    const [metricsSummary, setMetricsSummary] = useState([]);
    const [metricsDetail, setMetricsDetail] = useState([]);
    const [metricsLoading, setMetricsLoading] = useState(false);
    const [metricsError, setMetricsError] = useState('');
    const [waybills, setWaybills] = useState([]);
    const [waybillsLoading, setWaybillsLoading] = useState(false);
    const [waybillsError, setWaybillsError] = useState('');
    const [modalOpen, setModalOpen] = useState(false);
    const [selectedDates, setSelectedDates] = useState(new Set());
    const [onlyPending, setOnlyPending] = useState(false);
    const [showPendingOnly, setShowPendingOnly] = useState(false);
    const [exportStats, setExportStats] = useState({ delivered: 0, pending: 0 });
    const [printPayload, setPrintPayload] = useState(null);
    const [ratePerDelivery, setRatePerDelivery] = useState('');
    const [deductionPerIssue, setDeductionPerIssue] = useState('');
    const [settlementLoading, setSettlementLoading] = useState(false);
    const [settlementError, setSettlementError] = useState('');
    const [latestSettlement, setLatestSettlement] = useState(null);
    const [settlementHistory, setSettlementHistory] = useState([]);
    const [reprintLoadingWaybill, setReprintLoadingWaybill] = useState('');
    const [reprintMessage, setReprintMessage] = useState('');
    const [reprintError, setReprintError] = useState('');

    useEffect(() => {
        if (selectedMessenger && searchTerm === selectedMessenger.accountName) {
            setSearchResults([]);
            setDropdownOpen(false);
            return;
        }
        if (!searchTerm || searchTerm.trim().length < 2) {
            setSearchResults([]);
            setDropdownOpen(false);
            return;
        }
        const handler = setTimeout(() => {
            searchMessengers(searchTerm)
                .then((data) => {
                    setSearchResults(data || []);
                    setDropdownOpen((data || []).length > 0);
                })
                .catch(() => {
                    setSearchResults([]);
                    setDropdownOpen(false);
                });
        }, 300);
        return () => clearTimeout(handler);
    }, [searchTerm, selectedMessenger]);

    const requestMetrics = useCallback((messenger, from, to) => {
        if (!messenger) return;
        const { start, end } = buildDateRange(from, to);
        if (!start || !end) return;
        setMetricsError('');
        fetchMessengerMetrics(
            messenger.accountCode,
            messenger.customerNetworkCode || messenger.orgCode || messenger.dispatchNetworkCode || messenger.siteCode || '',
            start,
            end
        )
            .then((data) => {
                setMetricsSummary(data.summary || []);
                setMetricsDetail(data.detail || []);
            })
            .catch((error) => {
                setMetricsError(error.message);
            })
            .finally(() => setMetricsLoading(false));
    }, []);

    const handleSelectMessenger = useCallback(
        (messenger) => {
            setSelectedMessenger(messenger);
            setDropdownOpen(false);
            setSearchTerm(messenger.accountName);
            setWaybills([]);
            setWaybillsError('');
            setShowPendingOnly(false);
            setSettlementError('');
            setLatestSettlement(null);
            requestMetrics(messenger, dateFrom, dateTo);
        },
        [dateFrom, dateTo, requestMetrics]
    );

    useEffect(() => {
        if (!selectedMessenger?.accountCode) return;

        fetchMessengerRate(selectedMessenger.accountCode)
            .then((response) => {
                const value = response?.data?.rate_per_delivery;
                setRatePerDelivery(value != null ? String(value) : '');
            })
            .catch(() => setRatePerDelivery(''));

        fetchSettlements(selectedMessenger.accountCode, 8)
            .then((response) => setSettlementHistory(response?.data || []))
            .catch(() => setSettlementHistory([]));
    }, [selectedMessenger]);

    useEffect(() => {
        if (selectedMessenger) {
            requestMetrics(selectedMessenger, dateFrom, dateTo);
        }
    }, [dateFrom, dateTo, selectedMessenger, requestMetrics]);

    const requestWaybills = useCallback(
        (messenger, from, to) => {
            if (!messenger) return;
            const { start, end } = buildDateRange(from, to);
            if (!start || !end) return;
            setWaybillsLoading(true);
            setWaybillsError('');
            fetchMessengerWaybills(
                messenger.accountCode,
                messenger.customerNetworkCode || messenger.orgCode || messenger.dispatchNetworkCode || messenger.siteCode || '',
                start,
                end
            )
                .then((records) => {
                    setWaybills(records || []);
                })
                .catch((error) => setWaybillsError(error.message))
                .finally(() => setWaybillsLoading(false));
        },
        []
    );

    const toggleDateSelection = useCallback((day) => {
        setSelectedDates((prev) => {
            const next = new Set(prev);
            if (next.has(day)) next.delete(day);
            else next.add(day);
            return next;
        });
    }, []);

    const openExportModal = useCallback(() => {
        const grouped = groupWaybillsByDay(waybills);
        setSelectedDates(new Set(Object.keys(grouped)));
        setOnlyPending(false);
        setExportStats({
            delivered: waybills.filter((w) => w.isSign === 1).length,
            pending: waybills.filter((w) => w.isSign !== 1).length
        });
        setModalOpen(true);
    }, [waybills]);

    useEffect(() => {
        if (!modalOpen) return;
        let delivered = 0;
        let pending = 0;
        waybills.forEach((w) => {
            const day = w.dispatchTime ? w.dispatchTime.split(' ')[0] : 'Desconocido';
            if (!selectedDates.has(day)) return;
            if (w.isSign === 1 && !onlyPending) delivered += 1;
            else if (w.isSign !== 1) pending += 1;
        });
        setExportStats({ delivered, pending });
    }, [modalOpen, selectedDates, onlyPending, waybills]);

    const filteredWaybills = useMemo(() => {
        if (!showPendingOnly) return waybills;
        return waybills.filter((item) => item.isSign !== 1);
    }, [waybills, showPendingOnly]);

    const visibleDelivered = useMemo(
        () => filteredWaybills.filter((item) => item.isSign === 1).length,
        [filteredWaybills]
    );
    const visiblePending = useMemo(
        () => filteredWaybills.filter((item) => item.isSign !== 1).length,
        [filteredWaybills]
    );

    useEffect(() => {
        if (!printPayload) return;
        document.body.classList.add('printing-table');
        const id = setTimeout(() => {
            window.print();
            document.body.classList.remove('printing-table');
            setPrintPayload(null);
            setModalOpen(false);
        }, 150);
        return () => {
            document.body.classList.remove('printing-table');
            clearTimeout(id);
        };
    }, [printPayload]);

    const confirmExport = useCallback(async () => {
        if (!selectedMessenger || selectedDates.size === 0) return;
        const filtered = waybills.filter((w) => {
            const day = w.dispatchTime ? w.dispatchTime.split(' ')[0] : 'Desconocido';
            if (!selectedDates.has(day)) return false;
            if (onlyPending) return w.isSign !== 1;
            return true;
        });
        if (!filtered.length) return;

        let addressMap = {};
        if (onlyPending) {
            const ids = filtered.map((w) => w.waybillNo);
            try {
                addressMap = await fetchAddressesForWaybills(ids);
            } catch (error) {
                console.error('No se pudieron obtener direcciones', error);
            }
        }

        const payload = {
            messengerName: selectedMessenger.accountName,
            onlyPending,
            selectedDates: Array.from(selectedDates),
            delivered: onlyPending ? 0 : exportStats.delivered,
            pending: exportStats.pending,
            rows: filtered.map((item) => ({
                waybillNo: item.waybillNo,
                dispatchTime: item.dispatchTime,
                city: item.receiverCitye,
                status: translateStatus(item.status),
                signTime: item.signTime,
                address: addressMap[item.waybillNo]
            }))
        };
        setPrintPayload(payload);
    }, [selectedMessenger, selectedDates, onlyPending, waybills, exportStats]);

    const metricsCards = useMemo(() => {
        if (!metricsSummary || metricsSummary.length === 0) return [];
        const metrics = metricsSummary[0];
        const dispatchTotal = metrics.dispatchTotal || 0;
        const signTotal = metrics.signTotal || 0;
        const nosignTotal = metrics.nosignTotal || 0;
        const signRate = dispatchTotal ? ((signTotal / dispatchTotal) * 100).toFixed(2) + '%' : '0%';

        return [
            { title: 'Despachos Asignados', value: dispatchTotal, accent: 'var(--text-main)' },
            { title: 'Entregas Firmadas', value: signTotal, accent: 'var(--success)' },
            { title: 'Pendientes / Sin Firma', value: nosignTotal, accent: 'var(--warning)' },
            { title: 'Tasa de Efectividad', value: signRate, accent: 'var(--accent-color)' }
        ];
    }, [metricsSummary]);

    const groupedWaybillDays = useMemo(() => groupWaybillsByDay(waybills), [waybills]);

    const saveRate = useCallback(async () => {
        if (!selectedMessenger?.accountCode) return;
        setSettlementLoading(true);
        setSettlementError('');
        try {
            const response = await setMessengerRate(
                selectedMessenger.accountCode,
                selectedMessenger.accountName,
                Number(ratePerDelivery || 0)
            );
            const saved = response?.data?.rate_per_delivery;
            setRatePerDelivery(saved != null ? String(saved) : String(ratePerDelivery || '0'));
        } catch (error) {
            setSettlementError(error.message || 'No se pudo guardar la tarifa.');
        } finally {
            setSettlementLoading(false);
        }
    }, [selectedMessenger, ratePerDelivery]);

    const generateCurrentSettlement = useCallback(async () => {
        if (!selectedMessenger?.accountCode) return;
        const { start, end } = buildDateRange(dateFrom, dateTo);
        if (!start || !end) {
            setSettlementError('Rango de fechas inválido para liquidación.');
            return;
        }

        setSettlementLoading(true);
        setSettlementError('');
        try {
            const response = await generateSettlement({
                account_code: selectedMessenger.accountCode,
                account_name: selectedMessenger.accountName,
                network_code: selectedMessenger.customerNetworkCode || selectedMessenger.orgCode || selectedMessenger.dispatchNetworkCode || selectedMessenger.siteCode || '',
                start_time: start,
                end_time: end,
                deduction_per_issue: Number(deductionPerIssue || 0),
                rate_per_delivery: Number(ratePerDelivery || 0)
            });

            const generated = response?.data;
            setLatestSettlement(generated || null);

            const historyResp = await fetchSettlements(selectedMessenger.accountCode, 8);
            setSettlementHistory(historyResp?.data || []);
        } catch (error) {
            setSettlementError(error.message || 'No se pudo generar la liquidación.');
        } finally {
            setSettlementLoading(false);
        }
    }, [selectedMessenger, dateFrom, dateTo, deductionPerIssue, ratePerDelivery]);

    const removeSettlement = useCallback(async (settlementId) => {
        if (!selectedMessenger?.accountCode) return;
        setSettlementLoading(true);
        setSettlementError('');
        try {
            await deleteSettlement(settlementId);
            const historyResp = await fetchSettlements(selectedMessenger.accountCode, 8);
            const history = historyResp?.data || [];
            setSettlementHistory(history);
            setLatestSettlement((prev) => (prev?.id === settlementId ? null : prev));
        } catch (error) {
            setSettlementError(error.message || 'No se pudo eliminar la liquidación.');
        } finally {
            setSettlementLoading(false);
        }
    }, [selectedMessenger]);

    const reprintSingleWaybill = useCallback(async (waybillNo) => {
        const target = String(waybillNo || '').trim();
        if (!target) return;

        setReprintLoadingWaybill(target);
        setReprintError('');
        setReprintMessage('');

        try {
            const response = await reprintWaybills([target], 'small');
            const pdfUrl = response?.data?.pdf_url;
            if (!pdfUrl) {
                throw new Error('No se recibió la URL de reimpresión.');
            }

            const popup = window.open(pdfUrl, '_blank', 'noopener,noreferrer');
            if (!popup) {
                window.location.href = pdfUrl;
            }
            setReprintMessage(`Reimpresión generada para ${target}.`);
        } catch (error) {
            setReprintError(error.message || 'No se pudo reimprimir la guía.');
        } finally {
            setReprintLoadingWaybill('');
        }
    }, []);

    const reprintVisibleWaybills = useCallback(async (waybillNos) => {
        const targets = Array.isArray(waybillNos)
            ? waybillNos.map((item) => String(item || '').trim()).filter(Boolean)
            : [];

        if (!targets.length) return;

        setReprintLoadingWaybill('__BULK__');
        setReprintError('');
        setReprintMessage('');

        try {
            const response = await reprintWaybills(targets, 'small');
            const pdfUrl = response?.data?.pdf_url;
            if (!pdfUrl) {
                throw new Error('No se recibió la URL de reimpresión.');
            }

            const popup = window.open(pdfUrl, '_blank', 'noopener,noreferrer');
            if (!popup) {
                window.location.href = pdfUrl;
            }
            setReprintMessage(`Reimpresión masiva generada (${targets.length} guía${targets.length > 1 ? 's' : ''}).`);
        } catch (error) {
            setReprintError(error.message || 'No se pudo generar la reimpresión masiva.');
        } finally {
            setReprintLoadingWaybill('');
        }
    }, []);

    return {
        searchTerm,
        setSearchTerm,
        searchResults,
        dropdownOpen,
        handleSelectMessenger,
        selectedMessenger,
        dateFrom,
        setDateFrom,
        dateTo,
        setDateTo,
        metricsSummary,
        metricsDetail,
        metricsLoading,
        metricsError,
        requestWaybills,
        waybills,
        waybillsLoading,
        waybillsError,
        openExportModal,
        modalOpen,
        setModalOpen,
        selectedDates,
        toggleDateSelection,
        setSelectedDates,
        onlyPending,
        setOnlyPending,
        showPendingOnly,
        setShowPendingOnly,
        filteredWaybills,
        visibleDelivered,
        visiblePending,
        exportStats,
        confirmExport,
        groupedWaybillDays,
        printPayload,
        metricsCards,
        ratePerDelivery,
        setRatePerDelivery,
        deductionPerIssue,
        setDeductionPerIssue,
        settlementLoading,
        settlementError,
        latestSettlement,
        settlementHistory,
        reprintLoadingWaybill,
        reprintMessage,
        reprintError,
        saveRate,
        generateCurrentSettlement,
        removeSettlement,
        reprintSingleWaybill,
        reprintVisibleWaybills
    };
}
