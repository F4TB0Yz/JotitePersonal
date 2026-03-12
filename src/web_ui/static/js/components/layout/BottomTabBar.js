import { html } from '../../lib/ui.js';

const TAB_ITEMS = [
    { id: 'inicio',     label: 'Inicio',      icon: '🏠' },
    { id: 'reportes',   label: 'PDF',         icon: '📄' },
    { id: 'dashboard',  label: 'Pendientes',  icon: '📦' },
    { id: 'devoluciones', label: 'Devoluc.',  icon: '↩️' },
    { id: 'alertas',    label: 'Alertas',     icon: '⚠️' },
    { id: 'mensajeros', label: 'Mensajeros',  icon: '🛵' },
    { id: 'kpis',       label: 'KPIs',        icon: '📊' },
];

export default function BottomTabBar({ activeView, onChange }) {
    return html`
        <nav className="bottom-tab-bar no-print" aria-label="Navegación principal">
            ${TAB_ITEMS.map((tab) => html`
                <button
                    key=${tab.id}
                    type="button"
                    className=${`bottom-tab ${activeView === tab.id ? 'active' : ''}`}
                    onClick=${() => onChange(tab.id)}
                    aria-label=${tab.label}
                    aria-current=${activeView === tab.id ? 'page' : undefined}
                >
                    <span className="bottom-tab-icon">${tab.icon}</span>
                    <span className="bottom-tab-label">${tab.label}</span>
                </button>
            `)}
        </nav>
    `;
}
