import { html, useEffect, useState } from './lib/ui.js';
import TopNavbar from './components/layout/TopNavbar.js';
import BottomTabBar from './components/layout/BottomTabBar.js';
import HomeView from './components/dashboard/HomeView.js';
import WaybillProcessorView from './components/process/WaybillProcessorView.js';
import PendingDashboardView from './components/dashboard/PendingDashboardView.js';
import ReturnsView from './components/dashboard/ReturnsView.js';
import MessengerAdminView from './components/admin/MessengerAdminView.js';
import TemuAlertCenter from './components/dashboard/TemuAlertCenter.js';
import KpiDashboardView from './components/dashboard/KpiDashboardView.js';
import GlobalOverlays from './components/layout/GlobalOverlays.js';
import useAppNotifications from './hooks/useAppNotifications.js';

export default function App() {
    const [activeView, setActiveView] = useState('inicio');
    const { notifications, unreadCount, markAllRead } = useAppNotifications();

    const handleOpenAlerts = () => setActiveView('alertas');

    return html`
        <div className="app-root">
            ${html`<${TopNavbar}
                activeView=${activeView}
                onChange=${setActiveView}
                notifications=${notifications}
                unreadCount=${unreadCount}
                onOpenAlerts=${handleOpenAlerts}
                onMarkAllRead=${markAllRead}
            />`}
            <div className="app-container">
                <section className="view-section active">
                    ${(() => {
                        switch (activeView) {
                            case 'inicio': return html`<${HomeView} />`;
                            case 'reportes': return html`<${WaybillProcessorView} />`;
                            case 'dashboard': return html`<${PendingDashboardView} />`;
                            case 'devoluciones': return html`<${ReturnsView} />`;
                            case 'alertas': return html`<${TemuAlertCenter} />`;
                            case 'mensajeros': return html`<${MessengerAdminView} />`;
                            case 'kpis': return html`<${KpiDashboardView} />`;
                            default: return null;
                        }
                    })()}
                </section>
            </div>
            
            <${BottomTabBar} activeView=${activeView} onChange=${setActiveView} />
            <${GlobalOverlays} />
        </div>
    `;
}
