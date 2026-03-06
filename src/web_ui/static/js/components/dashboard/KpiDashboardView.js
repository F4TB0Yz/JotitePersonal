import { html, useEffect } from '../../lib/ui.js';
import { useKpiDashboard } from '../../hooks/useKpiDashboard.js';
import DateRangePicker from '../shared/DateRangePicker.js';
import { formatCurrencyCOP, formatDateTimeLabel } from '../../utils/formatters.js';

function formatPercent(value) {
    const safe = Number(value || 0);
    return `${safe.toFixed(2)}%`;
}

function formatHours(value) {
    const safe = Number(value || 0);
    return `${safe.toFixed(2)} h`;
}

export default function KpiDashboardView({ isActive }) {
    const {
        startDate,
        setStartDate,
        endDate,
        setEndDate,
        rankingLimit,
        setRankingLimit,
        loading,
        error,
        data,
        fetchKpis
    } = useKpiDashboard();

    useEffect(() => {
        if (!isActive) return;
        fetchKpis();
    }, [isActive, fetchKpis]);

    const summary = data.summary || {};
    const ranking = data.ranking || [];
    const novedades = data.novedades || { by_type: [], by_status: [] };
    const trend = data.trend || [];

    return html`
        <main className="kpi-main">
            <div className="kpi-shell">
                <div className="kpi-header">
                    <div>
                        <h2>KPIs Históricos</h2>
                        <p>Indicadores de efectividad, rendimiento de mensajeros y comportamiento de novedades.</p>
                    </div>
                    <form className="kpi-filters" onSubmit=${(event) => { event.preventDefault(); fetchKpis(); }}>
                        <${DateRangePicker}
                            label="Rango"
                            dateFrom=${startDate}
                            dateTo=${endDate}
                            onDateChange=${(from, to) => {
                                setStartDate(from);
                                setEndDate(to);
                            }}
                        />
                        <label>
                            Top ranking
                            <input
                                type="number"
                                min="3"
                                max="20"
                                value=${rankingLimit}
                                onChange=${(event) => setRankingLimit(Number(event.target.value || 10))}
                            />
                        </label>
                        <button type="submit" className="primary-btn" disabled=${loading}>
                            ${loading ? 'Actualizando…' : 'Actualizar KPIs'}
                        </button>
                    </form>
                </div>

                <section className="kpi-cards">
                    <article className="kpi-card">
                        <span className="kpi-card-value">${formatPercent(summary.effectiveness_rate)}</span>
                        <span className="kpi-card-label">Efectividad</span>
                    </article>
                    <article className="kpi-card">
                        <span className="kpi-card-value">${formatHours(summary.avg_delivery_hours)}</span>
                        <span className="kpi-card-label">Tiempo promedio entrega</span>
                    </article>
                    <article className="kpi-card">
                        <span className="kpi-card-value">${summary.total_delivered || 0}</span>
                        <span className="kpi-card-label">Entregadas</span>
                    </article>
                    <article className="kpi-card">
                        <span className="kpi-card-value">${summary.total_pending || 0}</span>
                        <span className="kpi-card-label">Pendientes</span>
                    </article>
                    <article className="kpi-card">
                        <span className="kpi-card-value">${formatCurrencyCOP(summary.total_amount || 0)}</span>
                        <span className="kpi-card-label">Monto liquidado</span>
                    </article>
                    <article className="kpi-card muted">
                        <span className="kpi-card-value">${summary.novedades || 0}</span>
                        <span className="kpi-card-label">Novedades registradas</span>
                    </article>
                </section>

                ${error ? html`<div className="kpi-error">${error}</div>` : null}

                <section className="kpi-grid">
                    <article className="kpi-panel">
                        <header>
                            <h3>Ranking de mensajeros</h3>
                        </header>
                        <div className="kpi-table-wrap">
                            <table className="kpi-table">
                                <thead>
                                    <tr>
                                        <th>Mensajero</th>
                                        <th>Entregadas</th>
                                        <th>Total</th>
                                        <th>Efectividad</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${ranking.length === 0
                                        ? html`<tr><td colSpan="4" className="kpi-empty">Sin datos en el rango.</td></tr>`
                                        : ranking.map((item) => html`
                                            <tr>
                                                <td>${item.account_name || item.account_code || 'Sin nombre'}</td>
                                                <td>${item.total_delivered || 0}</td>
                                                <td>${item.total_waybills || 0}</td>
                                                <td>${formatPercent(item.effectiveness_rate)}</td>
                                            </tr>
                                        `)}
                                </tbody>
                            </table>
                        </div>
                    </article>

                    <article className="kpi-panel">
                        <header>
                            <h3>Novedades por tipo</h3>
                        </header>
                        <div className="kpi-list">
                            ${(novedades.by_type || []).length === 0
                                ? html`<div className="kpi-empty">No hay novedades para este periodo.</div>`
                                : (novedades.by_type || []).map((row) => html`
                                    <div className="kpi-list-row">
                                        <span>${row.type}</span>
                                        <strong>${row.count}</strong>
                                    </div>
                                `)}
                        </div>
                    </article>

                    <article className="kpi-panel span-2">
                        <header>
                            <h3>Tendencia diaria</h3>
                            <small>Última actualización: ${formatDateTimeLabel(data.generated_at)}</small>
                        </header>
                        <div className="kpi-table-wrap">
                            <table className="kpi-table">
                                <thead>
                                    <tr>
                                        <th>Fecha</th>
                                        <th>Liquidaciones</th>
                                        <th>Guías</th>
                                        <th>Entregadas</th>
                                        <th>Novedades</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${trend.length === 0
                                        ? html`<tr><td colSpan="5" className="kpi-empty">Sin tendencia para mostrar.</td></tr>`
                                        : trend.map((item) => html`
                                            <tr>
                                                <td>${item.date}</td>
                                                <td>${item.settlements || 0}</td>
                                                <td>${item.waybills || 0}</td>
                                                <td>${item.delivered || 0}</td>
                                                <td>${item.novedades || 0}</td>
                                            </tr>
                                        `)}
                                </tbody>
                            </table>
                        </div>
                    </article>
                </section>
            </div>
        </main>
    `;
}