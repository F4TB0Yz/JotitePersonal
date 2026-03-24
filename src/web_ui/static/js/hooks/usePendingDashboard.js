import { useState, useCallback, useEffect, useRef } from '../lib/ui.js';
import { DEFAULT_NETWORK_CODE } from '../utils/constants.js';
import { toISODateInput, buildDateRange } from '../utils/formatters.js';
import { fetchPendingWaybills, fetchCellDetails } from '../services/networkService.js';

const DATE_MODE_ARRIVAL = 'arrival';
const DATE_MODE_ASSIGNMENT = 'assignment';

/** @type {{ summary: object, dates: string[], rows: object[] }} */
const EMPTY_MATRIX = { summary: { total: 0, old: 0, unassigned: 0 }, dates: [], rows: [] };

/**
 * Extracts the column date list from the API response, falling back to
 * deriving it dynamically from the row dictionaries if the backend omitted it.
 *
 * @param {object} data - Raw API response object.
 * @returns {string[]} Sorted list of unique date strings.
 */
function _resolveDates(data) {
    const fromSummary = data.dates || data.summary?.dates || [];
    if (fromSummary.length > 0) return fromSummary;
    if (!data.rows?.length) return [];

    const unique = new Set();
    data.rows.forEach((row) => {
        Object.keys(row.dates || row.data || {}).forEach((d) => unique.add(d));
    });
    return Array.from(unique).filter((d) => d !== 'total').sort();
}

/**
 * Core hook for the Pending Dashboard. Manages filter state, fetches the
 * matrix data, and exposes the lazy cell-detail loader.
 *
 * Intentionally does NOT manage waybill detail, phone, or messenger-contact
 * state — those concerns live in useWaybillDetails.
 *
 * @returns {object} Dashboard state and action API.
 */
export function usePendingDashboard() {
    const today = toISODateInput(new Date());
    const [networkCode, setNetworkCode] = useState(DEFAULT_NETWORK_CODE);
    const [startDate, setStartDate] = useState(today);
    const [endDate, setEndDate] = useState(today);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [matrixData, setMatrixData] = useState(EMPTY_MATRIX);
    const [subtitle, setSubtitle] = useState('');
    const [dateMode, setDateMode] = useState(DATE_MODE_ASSIGNMENT);
    const [selectedStaff, setSelectedStaff] = useState('ALL');
    const [selectedCell, setSelectedCell] = useState(null);
    const [cellLoading, setCellLoading] = useState(false);

    // TD-15: Prevents the dateMode effect from firing on the initial mount,
    // where fetchDashboard will have already run via the mount effect below.
    const isMounted = useRef(false);

    const fetchDashboard = useCallback(() => {
        if (!networkCode || !startDate || !endDate) {
            setError('Completa todos los campos');
            return;
        }
        const { start, end } = buildDateRange(startDate, endDate);
        setLoading(true);
        setError('');
        setSelectedCell(null);

        fetchPendingWaybills(networkCode, start, end, dateMode)
            .then((data) => {
                setMatrixData({
                    summary: data.summary || EMPTY_MATRIX.summary,
                    dates: _resolveDates(data),
                    rows: data.rows || [],
                });
                setSubtitle(`Punto: ${networkCode} | Periodo: ${startDate} a ${endDate}`);
            })
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [networkCode, startDate, endDate, dateMode]);

    // Initial fetch on mount — runs exactly once.
    useEffect(() => {
        fetchDashboard();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Re-fetch on dateMode change, but skip the mount cycle (isMounted guard).
    useEffect(() => {
        if (!isMounted.current) {
            isMounted.current = true;
            return;
        }
        fetchDashboard();
    }, [dateMode]); // eslint-disable-line react-hooks/exhaustive-deps

    const staffOptions = matrixData.rows.map((r) => r.staff);

    const displayedRows = selectedStaff === 'ALL' || !selectedStaff
        ? (matrixData.rows || [])
        : (matrixData.rows || []).filter(r => r.staff === selectedStaff);

    const derivedSummary = {
        ...(matrixData?.summary || {}),
        total: displayedRows.reduce((sum, row) => sum + (row.total || 0), 0),
        totalStaff: displayedRows.length,
        old: displayedRows.reduce((sum, row) => sum + (row.old || 0), 0)
    };

    const tableData = {
        dates: matrixData.dates,
        rows: displayedRows,
    };

    /**
     * Returns a sample waybill number for a given staff, if the backend provides one.
     * @param {string} staffValue
     * @returns {string}
     */
    const getSampleWaybillForStaff = useCallback((staffValue) => {
        const row = matrixData.rows.find((r) => r.staff === staffValue);
        return row?.sampleWaybill || '';
    }, [matrixData.rows]);

    /**
     * Lazy-loads the individual waybill records for a specific staff × date cell.
     * @param {string} staff
     * @param {string} day - ISO date string, or "ALL".
     */
    const loadCellDetails = useCallback((staff, day) => {
        setCellLoading(true);
        const { start, end } = buildDateRange(startDate, endDate);

        fetchCellDetails(networkCode, start, end, staff, day, dateMode)
            .then((data) => {
                // /api/network/waybills/details returns a flat WaybillDTO[]
                const records = Array.isArray(data) ? data : [];
                setSelectedCell({ staff, day, records });
            })
            .catch((err) => {
                console.error('Error fetching cell details:', err);
                setSelectedCell(null);
            })
            .finally(() => setCellLoading(false));
    }, [networkCode, startDate, endDate, dateMode]);

    return {
        // Filter state
        dateMode,
        setDateMode,
        dateModes: { arrival: DATE_MODE_ARRIVAL, assignment: DATE_MODE_ASSIGNMENT },
        selectedStaff,
        setSelectedStaff,
        networkCode,
        setNetworkCode,
        startDate,
        setStartDate,
        endDate,
        setEndDate,
        // Fetch
        fetchDashboard,
        loading,
        error,
        subtitle,
        // Derived data
        staffOptions,
        summary: derivedSummary,
        tableData,
        matrixData,
        // Cell lazy-load
        loadCellDetails,
        selectedCell,
        setSelectedCell,
        cellLoading,
        getSampleWaybillForStaff,
    };
}
