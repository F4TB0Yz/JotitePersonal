import { get } from './http.js';

export function fetchTemuAlerts({
    thresholdHours = 96,
    windowHours = 12,
    includeOverdue = true
} = {}) {
    const params = new URLSearchParams();
    if (thresholdHours) params.set('threshold_hours', thresholdHours);
    if (windowHours) params.set('window_hours', windowHours);
    params.set('include_overdue', includeOverdue ? 'true' : 'false');
    const queryString = params.toString();
    const url = queryString ? `/api/alerts/temu?${queryString}` : '/api/alerts/temu';
    return get(url);
}
