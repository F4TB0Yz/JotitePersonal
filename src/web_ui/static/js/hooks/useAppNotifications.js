import { useState, useEffect } from '../lib/ui.js';
import { initNotificationSocket, stopNotificationSocket } from '../services/notificationService.js';

export default function useAppNotifications() {
    const [notifications, setNotifications] = useState([]);
    const [unreadCount, setUnreadCount] = useState(0);

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

    const markAllRead = () => setUnreadCount(0);

    return { notifications, unreadCount, markAllRead };
}
