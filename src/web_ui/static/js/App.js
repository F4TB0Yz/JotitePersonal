import { html, useEffect, useState } from './lib/ui.js';
import TopNavbar from './components/layout/TopNavbar.js';
import BottomTabBar from './components/layout/BottomTabBar.js';
import WaybillProcessorView from './components/process/WaybillProcessorView.js';
import PendingDashboardView from './components/dashboard/PendingDashboardView.js';
import MessengerAdminView from './components/admin/MessengerAdminView.js';
import TemuAlertCenter from './components/dashboard/TemuAlertCenter.js';
import KpiDashboardView from './components/dashboard/KpiDashboardView.js';
import NovedadesModal from './components/shared/NovedadesModal.js';
import WaybillQueryModal from './components/shared/WaybillQueryModal.js';
import FloatingBarcodeScanner from './components/shared/FloatingBarcodeScanner.js';
import FloatingReprintButton from './components/shared/FloatingReprintButton.js';
import CommandPalette from './components/shared/CommandPalette.js';
import { initNotificationSocket, stopNotificationSocket } from './services/notificationService.js';

export default function App() {
    const [activeView, setActiveView] = useState('reportes');
    const [notifications, setNotifications] = useState([]);
    const [unreadCount, setUnreadCount] = useState(0);

    useEffect(() => {
        const onNavigate = (event) => {
            const nextView = event?.detail?.view;
            if (!nextView) return;
            setActiveView(nextView);
        };

        window.addEventListener('navigate-view', onNavigate);
        return () => window.removeEventListener('navigate-view', onNavigate);
    }, []);

    useEffect(() => {
        initNotificationSocket();
        return () => stopNotificationSocket();
    }, []);

    useEffect(() => {
        const onTemuBreach = (event) => {
            const payload = event?.detail;
            if (!payload?.billcode) return;

            setNotifications((prev) => {
                const exists = prev.some(
                    (item) => item.billcode === payload.billcode && (item.detectedAt || item.predicted96At) === (payload.detectedAt || payload.predicted96At)
                );
                if (exists) return prev;
                const next = [payload, ...prev];
                return next.slice(0, 50);
            });
            setUnreadCount((prev) => Math.min(prev + 1, 999));
        };

        window.addEventListener('temu-breach-predicted', onTemuBreach);
        return () => window.removeEventListener('temu-breach-predicted', onTemuBreach);
    }, []);

    const handleOpenAlerts = () => setActiveView('alertas');
    const handleMarkAllRead = () => setUnreadCount(0);

    return html`
        <div className="app-root">
            ${html`<${TopNavbar}
                activeView=${activeView}
                onChange=${setActiveView}
                notifications=${notifications}
                unreadCount=${unreadCount}
                onOpenAlerts=${handleOpenAlerts}
                onMarkAllRead=${handleMarkAllRead}
            />`}
            <div className="app-container">
                <section className=${`view-section ${activeView === 'reportes' ? 'active' : ''}`}>
                    <${WaybillProcessorView} isActive=${activeView === 'reportes'} />
                </section>
                <section className=${`view-section ${activeView === 'dashboard' ? 'active' : ''}`}>
                    <${PendingDashboardView} isActive=${activeView === 'dashboard'} />
                </section>
                <section className=${`view-section ${activeView === 'alertas' ? 'active' : ''}`}>
                    <${TemuAlertCenter} isActive=${activeView === 'alertas'} />
                </section>
                <section className=${`view-section ${activeView === 'mensajeros' ? 'active' : ''}`}>
                    <${MessengerAdminView} isActive=${activeView === 'mensajeros'} />
                </section>
                <section className=${`view-section ${activeView === 'kpis' ? 'active' : ''}`}>
                    <${KpiDashboardView} isActive=${activeView === 'kpis'} />
                </section>
            </div>
            
            <${BottomTabBar} activeView=${activeView} onChange=${setActiveView} />
            <${NovedadesModal} />
            <${WaybillQueryModal} />
            ${activeView === 'reportes' ? html`<${FloatingReprintButton} /><${FloatingBarcodeScanner} />` : null}
            <${CommandPalette} />
        </div>
    `;
}
