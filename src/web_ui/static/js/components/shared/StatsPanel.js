import { html } from '../../lib/ui.js';

export default function StatsPanel({ stats }) {
    if (!stats.visible) return null;
    return html`
        <div className="stats" aria-live="polite">
            <div className="stat-box">
                <span className="stat-number">${stats.total}</span>
                <span className="stat-label">Total</span>
            </div>
            <div className="stat-box success">
                <span className="stat-number">${stats.delivered}</span>
                <span className="stat-label">Entregados</span>
            </div>
            <div className="stat-box warning">
                <span className="stat-number">${stats.pending}</span>
                <span className="stat-label">En Tránsito</span>
            </div>
        </div>
    `;
}
