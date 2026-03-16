import { useState, useEffect, useMemo, useCallback, useRef } from '../lib/ui.js';
import { parseWaybillInput, parseInternalDate } from '../utils/formatters.js';
import { searchMessengers } from '../services/messengerService.js';

function filterCard(record, filterTab, from, to) {
    const matchesStatus =
        filterTab === 'all' ||
        (filterTab === 'delivered' && record.is_delivered) ||
        (filterTab === 'pending' && !record.is_delivered);

    if (!matchesStatus) return false;

    if (record.is_out_of_jurisdiction) {
        const exceptions = (record.exceptions || "").toLowerCase();
        const status = (record.status || "").toLowerCase();
        const isReturnPending = exceptions.includes("devolución") || status.includes("devolución");
        if (!isReturnPending) return false;
    }

    if (!from && !to) return true;
    if (record.loading) return true; // Mostrar placeholders mientras cargan
    
    const cardDate = parseInternalDate(record.arrival_punto6_time);
    if (!cardDate) return false;

    if (from) {
        const min = new Date(from);
        if (cardDate < min) return false;
    }
    if (to) {
        const max = new Date(to);
        if (cardDate > max) return false;
    }
    return true;
}

export function useWaybillProcessor() {
    const [inputValue, setInputValue] = useState('');
    const [cards, setCards] = useState([]);
    const [homeNode, setHomeNode] = useState({ home_node_id: '1009', home_node_name: 'Cund-Punto6' });
    const [statusMessage, setStatusMessage] = useState('Esperando ingreso...');
    const [isProcessing, setIsProcessing] = useState(false);
    const [filterTab, setFilterTab] = useState('all');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [showHeader, setShowHeader] = useState(true);
    const [showArribo, setShowArribo] = useState(true);
    const [mensajeroInput, setMensajeroInput] = useState('');
    const [mensajeroOptions, setMensajeroOptions] = useState([]);
    const [dropdownVisible, setDropdownVisible] = useState(false);

    const wsRef = useRef(null);
    const dropdownRef = useRef(null);
    const processedRef = useRef(0);

    const waybillList = useMemo(() => parseWaybillInput(inputValue), [inputValue]);

    const stats = useMemo(() => {
        const total = cards.length;
        const delivered = cards.filter((card) => card.is_delivered).length;
        return {
            total,
            delivered,
            pending: total - delivered,
            visible: total > 0
        };
    }, [cards]);

    const filteredCards = useMemo(() => {
        return cards.filter((card) => filterCard(card, filterTab, dateFrom, dateTo));
    }, [cards, filterTab, dateFrom, dateTo]);

    const closeWebSocket = useCallback(() => {
        if (wsRef.current) {
            wsRef.current.onclose = null;
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    const finalizeProcess = useCallback(() => {
        setIsProcessing(false);
    }, []);

    const startProcessing = useCallback(async () => {
        if (!waybillList.length || isProcessing) return;

        try {
            const check = await fetch('/api/waybills/details', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ waybills: ["PING"] })
            });
            if (check.status === 401) {
                setStatusMessage('Sesión expirada. Por favor inicia sesión nuevamente');
                return;
            }
        } catch (_) {}

        closeWebSocket();
        setCards(waybillList.map(wb => ({ waybill_no: wb, loading: true })));
        processedRef.current = 0;
        setStatusMessage(`Consultando 0 / ${waybillList.length} guías...`);
        setIsProcessing(true);

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/process`);
        wsRef.current = ws;

        ws.onopen = () => {
            ws.send(JSON.stringify({ waybills: waybillList }));
        };

        ws.onerror = () => {
            setStatusMessage('Error de conexión WebSocket.');
            closeWebSocket();
            finalizeProcess();
        };

        ws.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (!payload || typeof payload !== 'object') {
                    console.warn('Mensaje WS inesperado en useWaybillProcessor:', payload);
                    return;
                }

                if (payload.type === 'metadata') {
                    setHomeNode(payload.data);
                } else if (payload.type === 'result') {
                    processedRef.current += 1;
                    const record = payload.data || payload.result_dict || payload.results?.[0];
                    if (!record) {
                        console.warn('Resultado WS sin datos utilizables en useWaybillProcessor:', payload);
                        return;
                    }
                    setCards((prev) => {
                        const index = prev.findIndex(c => c.waybill_no === record.waybill_no);
                        if (index !== -1) {
                            const updated = [...prev];
                            updated[index] = { ...record, loading: false };
                            return updated;
                        }
                        return [...prev, { ...record, loading: false }];
                    });
                    setStatusMessage(`Consultando ${processedRef.current} / ${waybillList.length} guías...`);
                } else if (payload.type === 'done') {
                    setStatusMessage('¡Proceso completado!');
                    closeWebSocket();
                    finalizeProcess();
                } else if (payload.type === 'error') {
                    setStatusMessage(`Ocurrió un error: ${payload.message || 'Error desconocido'}`);
                    closeWebSocket();
                    finalizeProcess();
                } else {
                    console.warn('Tipo de mensaje WS no manejado en useWaybillProcessor:', payload);
                }
            } catch (err) {
                console.error('Error procesando mensaje WS en useWaybillProcessor:', err);
                setStatusMessage('Error al procesar respuesta del servidor.');
                closeWebSocket();
                finalizeProcess();
            }
        };

        ws.onclose = () => {
            setIsProcessing(false);
        };
    }, [waybillList, isProcessing, closeWebSocket, finalizeProcess]);

    useEffect(() => () => closeWebSocket(), [closeWebSocket]);

    useEffect(() => {
        if (!mensajeroInput || mensajeroInput.trim().length < 2) {
            setMensajeroOptions([]);
            setDropdownVisible(false);
            return;
        }
        const id = setTimeout(() => {
            searchMessengers(mensajeroInput)
                .then((data) => {
                    setMensajeroOptions(data || []);
                    setDropdownVisible((data || []).length > 0);
                })
                .catch(() => {
                    setMensajeroOptions([]);
                    setDropdownVisible(false);
                });
        }, 300);
        return () => clearTimeout(id);
    }, [mensajeroInput]);

    useEffect(() => {
        function handleClickOutside(event) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setDropdownVisible(false);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    useEffect(() => {
        const pending = cards.filter((card) => !card.loading && !card.is_delivered && card.status !== 'Error' && card.last_staff && card.last_staff !== 'N/A');
        const staffSet = new Set(pending.map((card) => card.last_staff));
        if (pending.length > 0 && staffSet.size === 1 && !mensajeroInput) {
            setMensajeroInput([...staffSet][0]);
        }
    }, [cards, mensajeroInput]);

    const selectMensajero = useCallback((name) => {
        setMensajeroInput(name);
        setDropdownVisible(false);
    }, []);

    return {
        inputValue,
        setInputValue,
        cards,
        filteredCards,
        stats,
        statusMessage,
        isProcessing,
        waybillCount: waybillList.length,
        filterTab,
        setFilterTab,
        dateFrom,
        setDateFrom,
        dateTo,
        setDateTo,
        showHeader,
        setShowHeader,
        showArribo,
        setShowArribo,
        mensajeroInput,
        setMensajeroInput,
        mensajeroOptions,
        dropdownVisible,
        dropdownRef,
        selectMensajero,
        startProcessing
    };
}
