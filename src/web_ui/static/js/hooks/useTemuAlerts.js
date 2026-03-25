import { useState, useEffect, useCallback, useMemo } from '../lib/ui.js';
import { fetchTemuAlerts } from '../services/alertService.js';

export default function useTemuAlerts({ isActive }) {
    const [windowHours, setWindowHours] = useState(12);
    const [includeOverdue, setIncludeOverdue] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [data, setData] = useState({ alerts: [], summary: {}, generatedAt: '' });
    const [realtimeNote, setRealtimeNote] = useState('');

    const loadData = useCallback(() => {
        setLoading(true);
        setError('');
        fetchTemuAlerts({ windowHours, includeOverdue })
            .then((response) => setData(response))
            .catch((err) => setError(err?.message || 'No se pudo cargar el monitoreo.'))
            .finally(() => setLoading(false));
    }, [windowHours, includeOverdue]);

    useEffect(() => {
        if (!isActive) return undefined;
        loadData();
        const interval = setInterval(loadData, 60 * 60 * 1000);
        return () => clearInterval(interval);
    }, [isActive, loadData]);

    useEffect(() => {
        const onPredictedBreach = (event) => {
            const payload = event?.detail;
            if (!payload?.billcode) return;

            setData((prev) => {
                const previousAlerts = prev.alerts || [];
                const alreadyExists = previousAlerts.some((item) => item.billcode === payload.billcode);
                if (alreadyExists) {
                    return prev;
                }

                const nextAlert = {
                    ...payload,
                    status: 'breached',
                    hoursToThreshold: 0,
                    hoursSinceEvent: Number(payload.hoursSinceEvent || 96),
                };

                return {
                    ...prev,
                    generatedAt: new Date().toISOString(),
                    alerts: [nextAlert, ...previousAlerts],
                    breachedCount: (prev.breachedCount || 0) + 1,
                };
            });

            setRealtimeNote(`Nueva crítica detectada: ${payload.billcode}`);
            setTimeout(() => setRealtimeNote(''), 7000);
        };

        window.addEventListener('temu-breach-predicted', onPredictedBreach);
        return () => window.removeEventListener('temu-breach-predicted', onPredictedBreach);
    }, []);

    return useMemo(() => ({ 
        windowHours, setWindowHours, 
        includeOverdue, setIncludeOverdue, 
        loading, error, data, realtimeNote, loadData 
    }), [windowHours, includeOverdue, loading, error, data, realtimeNote, loadData]);
}
