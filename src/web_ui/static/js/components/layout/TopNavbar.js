import { html, useState, useEffect } from '../../lib/ui.js';
import NotificationBell from './NotificationBell.js';

const NAV_ITEMS = [
    { id: 'reportes', label: 'Generador PDF' },
    { id: 'dashboard', label: 'Dashboard Pendientes' },
    { id: 'alertas', label: 'Alertas 96h' },
    { id: 'mensajeros', label: 'Gestión de Mensajeros' },
    { id: 'kpis', label: 'KPIs Históricos' }
];

export default function TopNavbar({ activeView, onChange, notifications = [], unreadCount = 0, onOpenAlerts, onMarkAllRead }) {
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    // Close menu when clicking outside
    useEffect(() => {
        if (!mobileMenuOpen) return;
        const close = () => setMobileMenuOpen(false);
        window.addEventListener('click', close, { once: true });
        return () => window.removeEventListener('click', close);
    }, [mobileMenuOpen]);

    return html`
        <nav className="top-navbar no-print">
            <div className="logo-container-nav">
                <h1>J&T<span>Express</span></h1>
            </div>
            <ul className="nav-links">
                ${NAV_ITEMS.map((item) =>
                    html`<li key=${item.id}>
                        <button
                            type="button"
                            className=${`nav-btn ${activeView === item.id ? 'active' : ''}`}
                            onClick=${() => onChange(item.id)}
                        >
                            ${item.label}
                        </button>
                    </li>`)}
            </ul>
            <div className="navbar-empty">
                <!-- Desktop: all action buttons visible -->
                <${NotificationBell}
                    notifications=${notifications}
                    unreadCount=${unreadCount}
                    onOpenAlerts=${onOpenAlerts}
                    onMarkAllRead=${onMarkAllRead}
                />
                <button
                    className="query-trigger-btn navbar-desktop-only"
                    onClick=${() => window.dispatchEvent(new CustomEvent('open-command-palette'))}
                    title="Búsqueda global (Ctrl+K)"
                >
                    ⌘K
                </button>
                <button 
                    className="query-trigger-btn navbar-desktop-only"
                    onClick=${() => window.dispatchEvent(new CustomEvent('open-query-modal'))}
                    title="Consultar Guía"
                >
                    🔍
                </button>
                <button 
                    className="novedades-trigger-btn navbar-desktop-only"
                    onClick=${() => window.dispatchEvent(new CustomEvent('open-novedades-modal'))}
                    title="Abrir Centro de Novedades"
                >
                    ⚠️ Novedades
                </button>

                <!-- Mobile: hamburger button for action menu -->
                <div className="navbar-mobile-menu-wrap">
                    <button
                        type="button"
                        className="navbar-mobile-hamburger"
                        aria-label="Más opciones"
                        aria-expanded=${mobileMenuOpen}
                        onClick=${(e) => { e.stopPropagation(); setMobileMenuOpen((v) => !v); }}
                    >
                        ☰
                    </button>
                    ${mobileMenuOpen ? html`
                        <div className="navbar-mobile-dropdown" onClick=${(e) => e.stopPropagation()}>
                            <button type="button" className="navbar-mobile-action"
                                onClick=${() => { setMobileMenuOpen(false); window.dispatchEvent(new CustomEvent('open-command-palette')); }}>
                                ⌘K Búsqueda global
                            </button>
                            <button type="button" className="navbar-mobile-action"
                                onClick=${() => { setMobileMenuOpen(false); window.dispatchEvent(new CustomEvent('open-query-modal')); }}>
                                🔍 Consultar Guía
                            </button>
                            <button type="button" className="navbar-mobile-action"
                                onClick=${() => { setMobileMenuOpen(false); window.dispatchEvent(new CustomEvent('open-novedades-modal')); }}>
                                ⚠️ Novedades
                            </button>
                        </div>
                    ` : null}
                </div>
            </div>
        </nav>
    `;
}
