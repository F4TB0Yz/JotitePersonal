import { useState, useCallback, useEffect } from '../lib/ui.js';
import { DEFAULT_NETWORK_CODE } from '../utils/constants.js';
import { toISODateInput, buildDateRange } from '../utils/formatters.js';
import { fetchPendingWaybills, fetchCellDetails } from '../services/networkService.js';

const DATE_MODE_ARRIVAL = 'arrival';
const DATE_MODE_ASSIGNMENT = 'assignment';

export function usePendingDashboard() {
    const today = toISODateInput(new Date());
    const [networkCode, setNetworkCode] = useState(DEFAULT_NETWORK_CODE);
    const [startDate, setStartDate] = useState(today);
    const [endDate, setEndDate] = useState(today);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    
    // Replace giant records array with clean matrix state
    const [matrixData, setMatrixData] = useState({ summary: { total: 0, old: 0, unassigned: 0 }, dates: [], rows: [] });
    
    const [subtitle, setSubtitle] = useState('');
    const [dateMode, setDateMode] = useState(DATE_MODE_ASSIGNMENT);
    const [selectedStaff, setSelectedStaff] = useState('ALL');

    // Lazy load state
    const [selectedCell, setSelectedCell] = useState(null);
    const [cellLoading, setCellLoading] = useState(false);

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
                let safeDates = data.dates || (data.summary && data.summary.dates) || [];

                // Si el backend no envió las columnas globales, las extraemos dinámicamente de las filas
                if (safeDates.length === 0 && data.rows && data.rows.length > 0) {
                    const uniqueDates = new Set();
                    data.rows.forEach(row => {
                        // Soporta tanto row.dates como row.data dependiendo de cómo el backend haya nombrado el diccionario
                        const rowDict = row.dates || row.data || {};
                        Object.keys(rowDict).forEach(d => uniqueDates.add(d));
                    });
                    // Ignoramos la llave 'total' si el backend la coló en el diccionario por accidente
                    safeDates = Array.from(uniqueDates).filter(d => d !== 'total').sort();
                }

                setMatrixData({
                    summary: data.summary || { total: 0, old: 0, unassigned: 0 },
                    dates: safeDates,
                    rows: data.rows || []
                });
                setSubtitle(`Punto: ${networkCode} | Periodo: ${startDate} a ${endDate}`);
            })
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [networkCode, startDate, endDate, dateMode]);

    useEffect(() => {
        fetchDashboard();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const staffOptions = (matrixData.rows || []).map(r => r.staff);

    const filteredRows = selectedStaff === 'ALL' 
        ? matrixData.rows 
        : matrixData.rows.filter(r => r.staff === selectedStaff);

    const tableData = {
        dates: matrixData.dates,
        rows: filteredRows
    };

    const getSampleWaybillForStaff = useCallback((staffValue) => {
        const row = matrixData.rows.find(r => r.staff === staffValue);
        // The backend should ideally provide a sample waybill, or we gracefully return an empty string.
        return row?.sampleWaybill || ''; 
    }, [matrixData.rows]);

    const loadCellDetails = useCallback((staff, day) => {
        setCellLoading(true);
        const { start, end } = buildDateRange(startDate, endDate);
        fetchCellDetails(networkCode, start, end, staff, day, dateMode)
            .then(data => {
                // Ensure robust data extraction whether it's wrapped in { records: [] } or just []
                const records = Array.isArray(data) ? data : (data.records || []);
                setSelectedCell({ staff, day, records });
            })
            .catch(err => {
                console.error('Error fetching cell details:', err);
                setSelectedCell(null);
            })
            .finally(() => {
                setCellLoading(false);
            });
    }, [networkCode, startDate, endDate, dateMode]);

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
        summary: matrixData.summary,
        tableData,
        matrixData,
        
        // Expose new lazy loading API and state
        loadCellDetails,
        selectedCell,
        setSelectedCell,
        cellLoading,
        getSampleWaybillForStaff
    };
}
