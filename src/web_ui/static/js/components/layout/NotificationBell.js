import { html, useEffect, useMemo, useRef, useState } from '../../lib/ui.js';
import { formatDateTimeLabel } from '../../utils/formatters.js';

function useOutsideClick(ref, handler) {
    useEffect(() => {
        const onClick = (event) => {
            if (!ref.current || ref.current.contains(event.target)) return;
            handler();
        };
        document.addEventListener('mousedown', onClick);
        return () => document.removeEventListener('mousedown', onClick);
    }, [ref, handler]);
}

export default function NotificationBell({ notifications = [], unreadCount = 0, onOpenAlerts, onMarkAllRead }) {
    const [open, setOpen] = useState(false);
    const containerRef = useRef(null);

    useOutsideClick(containerRef, () => setOpen(false));

    const latest = useMemo(() => notifications.slice(0, 12), [notifications]);

    const openAlertsAndClose = () => {
        onOpenAlerts?.();
        setOpen(false);
    };

    return html`
        <div className="notification-bell" ref=${containerRef}>
            <button
                type="button"
                className=${`query-trigger-btn notification-bell-trigger ${unreadCount > 0 ? 'has-unread' : ''}`}
                onClick=${() => {
                    const nextOpen = !open;
                    setOpen(nextOpen);
                    if (nextOpen && unreadCount > 0) {
                        onMarkAllRead?.();
                    }
                }}
                title="Notificaciones TEMU"
            >
                🔔
                ${unreadCount > 0 ? html`<span className="notification-badge">${unreadCount > 99 ? '99+' : unreadCount}</span>` : null}
            </button>

            ${open ? html`
                <div className="notification-dropdown">
                    <header className="notification-dropdown-header">
                        <strong>Alertas TEMU</strong>
                        <button type="button" className="notification-link" onClick=${openAlertsAndClose}>Ir al centro</button>
                    </header>
                    <div className="notification-dropdown-list">
                        ${latest.length === 0
                            ? html`<div className="notification-empty">Sin alertas recientes.</div>`
                            : latest.map((item) => html`
                                <button
                                    type="button"
                                    key=${`${item.billcode}-${item.detectedAt || item.predicted96At}`}
                                    className="notification-item"
                                    onClick=${openAlertsAndClose}
                                >
                                    <div className="notification-item-head">
                                        <strong>${item.billcode || 'Sin guía'}</strong>
                                        <span>≥96h</span>
                                    </div>
                                    <p>${item.customerName || 'Cliente desconocido'} · ${item.dutyName || item.managerDesc || 'Sin punto'}</p>
                                    <small>${formatDateTimeLabel(item.detectedAt || item.predicted96At)}</small>
                                </button>
                            `)}
                    </div>
                </div>
            ` : null}
        </div>
    `;
}
