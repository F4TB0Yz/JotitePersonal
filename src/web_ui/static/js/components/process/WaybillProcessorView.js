import { html } from '../../lib/ui.js';
import { useWaybillProcessor } from '../../hooks/useWaybillProcessor.js';
import WaybillCard from './WaybillCard.js';
import StatsPanel from '../shared/StatsPanel.js';
import DateRangePicker from '../shared/DateRangePicker.js';

const FILTERS = [
    { id: 'all', label: 'Todos' },
    { id: 'delivered', label: 'Entregados' },
    { id: 'pending', label: 'Pendientes' }
];

export default function WaybillProcessorView() {
    const {
        inputValue,
        setInputValue,
        cards,
        filteredCards,
        stats,
        statusMessage,
        isProcessing,
        waybillCount,
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
    } = useWaybillProcessor();

    const handlePrint = () => {
        window.print();
    };

    const printHeaderClasses = ['print-header', 'hidden-screen'];
    if (!showHeader) {
        printHeaderClasses.push('print-header--disabled');
    }

    const waybillPlaceholder = 'JTC000034865947\nJTC000033651331...';

    return html`
        <div className="processor-view">
        <aside className="sidebar no-print">
            <h3 className="sidebar-title">Configuración de Reporte</h3>
            <div className="input-section">
                <label htmlFor="waybills-input">Ingresa tus Guías (una por línea):</label>
                <textarea
                    id="waybills-input"
                    placeholder=${waybillPlaceholder}
                    value=${inputValue}
                    onChange=${(event) => setInputValue(event.target.value)}
                ></textarea>
                <button type="button" className="primary-btn" disabled=${isProcessing || waybillCount === 0} onClick=${startProcessing}>
                    ${isProcessing ? 'Procesando…' : 'Procesar Guías'}
                </button>
            </div>
            <div className="status-panel">
                <p id="status-message">${statusMessage}</p>
                <${StatsPanel} stats=${stats} />
            </div>
            <div className="actions-section">
                <h3>Exportar / Imprimir</h3>
                <div className="print-config">
                    <label className="checkbox-row">
                        <input type="checkbox" checked=${showHeader} onChange=${(e) => setShowHeader(e.target.checked)} />
                        Incluir título y mensajero en PDF
                    </label>
                    <label className="checkbox-row">
                        <input type="checkbox" checked=${showArribo} onChange=${(e) => setShowArribo(e.target.checked)} />
                        Mostrar Arribo a P6 en tarjetas
                    </label>
                    <label className="sidebar-helper">Mensajero (para PDF):</label>
                    <div className="autocomplete-wrapper" ref=${dropdownRef}>
                        <input
                            type="text"
                            className="sidebar-input"
                            value=${mensajeroInput}
                            onChange=${(event) => setMensajeroInput(event.target.value)}
                            placeholder="Escribe para buscar o auto-detect..."
                            autoComplete="off"
                        />
                        ${dropdownVisible
                            ? html`<ul className="autocomplete-dropdown">
                                ${mensajeroOptions.map((option) =>
                                    html`<li key=${option.accountCode} onMouseDown=${() => selectMensajero(option.accountName)}>
                                        ${option.accountName} (${option.customerNetworkName || 'Desconocido'})
                                    </li>`)}
                            </ul>`
                            : null}
                    </div>
                </div>
                <${DateRangePicker} 
                    label="Filtrar por Fecha (Arribo P6):"
                    dateFrom=${dateFrom} 
                    dateTo=${dateTo} 
                    onDateChange=${(start, end) => {
                        setDateFrom(start);
                        setDateTo(end);
                    }} 
                />
                <div className="filter-controls">
                    ${FILTERS.map((filter) =>
                        html`<button
                            type="button"
                            key=${filter.id}
                            className=${`filter-btn ${filterTab === filter.id ? 'active' : ''}`}
                            onClick=${() => setFilterTab(filter.id)}
                        >
                            ${filter.label}
                        </button>`)}
                </div>
                <div className="print-btn-wrapper">
                    <button type="button" className="secondary-btn" onClick=${handlePrint}>Imprimir / PDF</button>
                </div>
            </div>
        </aside>
        <main className=${`main-content ${showArribo ? '' : 'hide-arribo'}`}>
            <header className="header no-print">
                <h2>Resultados del Seguimiento</h2>
            </header>
            <div className=${printHeaderClasses.join(' ')}>
                <h1>Guías Pendientes</h1>
                <h2>Mensajero: <span>${mensajeroInput || '_________________'}</span></h2>
            </div>
            <div className="cards-grid">
                ${filteredCards.length === 0
                    ? html`<div className="empty-state">
                        <p>${cards.length === 0 ? 'Ingresa tus números de guía y presiona "Procesar"' : 'Sin resultados para los filtros seleccionados.'}</p>
                    </div>`
                    : filteredCards.map((card) => html`<${WaybillCard} key=${card.waybill_no} data=${card} showArribo=${showArribo} />`)}
            </div>
        </main>
        </div>
    `;
}
