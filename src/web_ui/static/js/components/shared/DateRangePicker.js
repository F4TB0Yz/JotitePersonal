import { html, useEffect, useRef } from '../../lib/ui.js';

export default function DateRangePicker({ dateFrom, dateTo, onDateChange, label = "Rango de Fechas" }) {
    const inputRef = useRef(null);
    const fpRef = useRef(null);

    useEffect(() => {
        if (!inputRef.current) return;

        // Inicializar flatpickr
        fpRef.current = flatpickr(inputRef.current, {
            mode: "range",
            dateFormat: "Y-m-d",
            defaultDate: [dateFrom, dateTo],
            locale: "es", // Español
            onChange: function(selectedDates) {
                if (selectedDates.length === 2) {
                    const fmt = (d) => {
                        const y = d.getFullYear();
                        const m = String(d.getMonth() + 1).padStart(2, '0');
                        const dDay = String(d.getDate()).padStart(2, '0');
                        return `${y}-${m}-${dDay}`;
                    };
                    onDateChange(fmt(selectedDates[0]), fmt(selectedDates[1]));
                }
            }
        });

        return () => {
            if (fpRef.current) fpRef.current.destroy();
        };
    }, []);

    // Sincronizar selección si cambian las props externamente
    useEffect(() => {
        if (fpRef.current && dateFrom && dateTo) {
            const currentDates = fpRef.current.selectedDates;
            const fmt = (d) => {
                const y = d.getFullYear();
                const m = String(d.getMonth() + 1).padStart(2, '0');
                const dDay = String(d.getDate()).padStart(2, '0');
                return `${y}-${m}-${dDay}`;
            };
            
            if (currentDates.length === 2) {
                const start = fmt(currentDates[0]);
                const end = fmt(currentDates[1]);
                if (start !== dateFrom || end !== dateTo) {
                    fpRef.current.setDate([dateFrom, dateTo], false);
                }
            } else {
                fpRef.current.setDate([dateFrom, dateTo], false);
            }
        }
    }, [dateFrom, dateTo]);

    return html`
        <div className="date-filter single-range">
            <label>
                ${label}
                <input 
                    type="text" 
                    ref=${inputRef} 
                    placeholder="Seleccionar rango..."
                    className="flatpickr-interactive-input"
                    readOnly="readonly"
                />
            </label>
        </div>
    `;
}
