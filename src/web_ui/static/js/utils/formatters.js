import { RATE_THRESHOLDS } from './constants.js';

export function parseWaybillInput(rawText) {
    if (!rawText) return [];
    return rawText
        .split('\n')
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
}

export function toISODateInput(date = new Date()) {
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().split('T')[0];
}

export function formatDateToSpanish(dateStr) {
    if (!dateStr) return 'N/A';
    const [rawDate] = dateStr.split(' ');
    if (!rawDate) return 'N/A';
    const [year, month, day] = rawDate.split('-');
    if (!year || !month || !day) return dateStr;
    const months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    const monthIndex = parseInt(month, 10) - 1;
    if (monthIndex < 0 || monthIndex > 11) return dateStr;
    return `${parseInt(day, 10)} de ${months[monthIndex]}`;
}

export function formatCity(cityField) {
    if (!cityField) return 'N/A';
    return cityField.split('|')[0];
}

export function pickRateColor(rate) {
    if (rate >= RATE_THRESHOLDS.success) return 'var(--success)';
    if (rate >= RATE_THRESHOLDS.warning) return 'var(--warning)';
    return 'var(--accent-color)';
}

export function calculateRate(total, success) {
    if (!total) return 0;
    return Number(((success / total) * 100).toFixed(2));
}

export function formatShortDate(dateStr) {
    if (!dateStr) return 'Sin Fecha';
    if (dateStr === 'Sin Fecha') return dateStr;
    const [year, month, day] = dateStr.split('-');
    if (!year || !month || !day) return dateStr;
    const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const monthIndex = parseInt(month, 10) - 1;
    if (monthIndex < 0 || monthIndex > 11) return dateStr;
    return `${day}-${months[monthIndex]}`;
}

export function buildDateRange(from, to) {
    const start = from ? `${from} 00:00:00` : '';
    const end = to ? `${to} 23:59:59` : '';
    return { start, end };
}

export function formatHours(value, decimals = 1) {
    if (typeof value !== 'number' || Number.isNaN(value)) return '—';
    return `${value.toFixed(decimals)} h`;
}

export function formatDateTimeLabel(dateStr) {
    if (!dateStr) return 'Sin registro';
    const parsed = new Date(dateStr);
    if (!Number.isNaN(parsed.getTime())) {
        return parsed.toLocaleString('es-CO', { hour12: false });
    }
    if (dateStr.includes('T')) {
        return dateStr.replace('T', ' ').split('.')[0];
    }
    return dateStr;
}

export function formatCurrencyCOP(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return '$ 0';
    return amount.toLocaleString('es-CO', {
        style: 'currency',
        currency: 'COP',
        maximumFractionDigits: 0
    });
}

export function parseInternalDate(dateStr) {
    if (!dateStr || dateStr === 'N/A') return null;
    try {
        const rawDate = dateStr.substring(0, 10);
        const parsed = new Date(`${rawDate}T00:00:00`);
        return isNaN(parsed.getTime()) ? null : parsed;
    } catch (_) {
        return null;
    }
}
