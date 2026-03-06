import { useState, useCallback, useMemo, useEffect } from '../lib/ui.js';
import { DEFAULT_NETWORK_CODE, DASHBOARD_MAX_DAYS_OLD } from '../utils/constants.js';
import { toISODateInput, buildDateRange } from '../utils/formatters.js';
import { fetchPendingWaybills } from '../services/networkService.js';

const DATE_MODE_ARRIVAL = 'arrival';
const DATE_MODE_ASSIGNMENT = 'assignment';

function normalizeStaff(value) {
    if (!value || value.trim() === '' || value === 'N/A') return 'Sin enrutar';
    return value.trim();
}

function normalizeDate(value) {
    if (!value || value === 'N/A') return 'Sin Fecha';
    return value.split(' ')[0];
}

function pickFirstDate(record, fields) {
    for (const field of fields) {
        const value = record?.[field];
        if (value && value !== 'N/A') return value;
    }
    return '';
}

function getRecordDateValue(record, mode) {
    if (mode === DATE_MODE_ASSIGNMENT) {
        return pickFirstDate(record, [
            'deliveryScanTimeLatest',
            'dispatchTime',
            'assignTime',
            'deliveryTime',
            'operateTime',
            'destArrivalTime',
            'dateTime',
            'deadLineTime',
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

export function usePendingDashboard() {
    const today = toISODateInput(new Date());
    const [networkCode, setNetworkCode] = useState(DEFAULT_NETWORK_CODE);
    const [startDate, setStartDate] = useState(today);
    const [endDate, setEndDate] = useState(today);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [records, setRecords] = useState([]);
    const [subtitle, setSubtitle] = useState('');
    const [dateMode, setDateMode] = useState(DATE_MODE_ASSIGNMENT);
    const [selectedStaff, setSelectedStaff] = useState('ALL');

    const fetchDashboard = useCallback(() => {
        if (!networkCode || !startDate || !endDate) {
            setError('Completa todos los campos');
            return;
        }
        const { start, end } = buildDateRange(startDate, endDate);
        setLoading(true);
        setError('');
        fetchPendingWaybills(networkCode, start, end)
            .then((data) => {
                setRecords(data.records || []);
                setSubtitle(`Punto: ${networkCode} | Periodo: ${startDate} a ${endDate}`);
            })
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [networkCode, startDate, endDate]);

    useEffect(() => {
        fetchDashboard();
    }, []);

    const staffOptions = useMemo(() => {
        const uniqueStaff = Array.from(
            new Set(records.map((item) => normalizeStaff(item.deliveryUser)))
        );
        return uniqueStaff.sort((a, b) => {
            if (a === 'Sin enrutar') return -1;
            if (b === 'Sin enrutar') return 1;
            return a.localeCompare(b);
        });
    }, [records]);

    const filteredRecords = useMemo(() => {
        if (selectedStaff === 'ALL') return records;
        return records.filter((item) => normalizeStaff(item.deliveryUser) === selectedStaff);
    }, [records, selectedStaff]);

    const getRecordsByCell = useCallback((staffValue, dayValue) => {
        const normalizedStaff = normalizeStaff(staffValue);
        const normalizedDay = !dayValue || dayValue === 'Sin Fecha' ? 'Sin Fecha' : normalizeDate(dayValue);
        return filteredRecords.filter((item) => {
            const staff = normalizeStaff(item.deliveryUser);
            const day = normalizeDate(getRecordDateValue(item, dateMode));
            return staff === normalizedStaff && day === normalizedDay;
        });
    }, [filteredRecords, dateMode]);

    const getRecordsByStaff = useCallback((staffValue) => {
        const normalizedStaff = normalizeStaff(staffValue);
        return filteredRecords.filter((item) => normalizeStaff(item.deliveryUser) === normalizedStaff);
    }, [filteredRecords]);

    const getSampleWaybillForStaff = useCallback((staffValue) => {
        const normalizedStaff = normalizeStaff(staffValue);
        const match = filteredRecords.find((item) => normalizeStaff(item.deliveryUser) === normalizedStaff);
        if (!match) return '';
        return match.waybillNo || match.billCode || match.orderId || '';
    }, [filteredRecords]);

    const summary = useMemo(() => {
        const todayDate = new Date();
        let total = 0;
        let old = 0;
        let unassigned = 0;
        filteredRecords.forEach((item) => {
            total += 1;
            const staff = normalizeStaff(item.deliveryUser);
            if (staff === 'Sin enrutar') unassigned += 1;
            const recordDate = normalizeDate(getRecordDateValue(item, dateMode));
            if (recordDate !== 'Sin Fecha') {
                const diff = Math.ceil(Math.abs(todayDate - new Date(recordDate)) / (1000 * 60 * 60 * 24));
                if (diff >= DASHBOARD_MAX_DAYS_OLD) old += 1;
            }
        });
        return { total, old, unassigned };
    }, [filteredRecords, dateMode]);

    const tableData = useMemo(() => {
        const staffMap = new Map();
        const dateSet = new Set();

        filteredRecords.forEach((item) => {
            const staff = normalizeStaff(item.deliveryUser);
            const day = normalizeDate(getRecordDateValue(item, dateMode));
            dateSet.add(day);
            if (!staffMap.has(staff)) staffMap.set(staff, { total: 0 });
            const staffRow = staffMap.get(staff);
            staffRow[day] = (staffRow[day] || 0) + 1;
            staffRow.total += 1;
        });

        const sortedDates = Array.from(dateSet).sort((a, b) => {
            if (a === 'Sin Fecha') return 1;
            if (b === 'Sin Fecha') return -1;
            return new Date(a) - new Date(b);
        });

        const rows = Array.from(staffMap.entries())
            .sort(([a], [b]) => {
                if (a === 'Sin enrutar') return -1;
                if (b === 'Sin enrutar') return 1;
                return b.localeCompare(a);
            })
            .map(([staff, data]) => ({ staff, data }));

        return { dates: sortedDates, rows };
    }, [filteredRecords, dateMode]);

    return {
        dateMode,
        setDateMode,
        dateModes: {
            arrival: DATE_MODE_ARRIVAL,
            assignment: DATE_MODE_ASSIGNMENT
        },
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
    };
}
