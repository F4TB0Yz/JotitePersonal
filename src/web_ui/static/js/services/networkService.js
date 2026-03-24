import { post } from './http.js';

/**
 * @typedef {Object} DashboardMatrixPayload
 * @property {string} networkCode    - Node network identifier.
 * @property {string} startTime      - ISO datetime range start (e.g. "2026-03-01 00:00:00").
 * @property {string} endTime        - ISO datetime range end   (e.g. "2026-03-31 23:59:59").
 * @property {0|1}   signType        - 0 = pending, 1 = signed.
 * @property {string} dateMode       - "assignment" | "arrival".
 */

/**
 * @typedef {Object} CellDetailPayload
 * @property {string}      networkCode  - Node network identifier.
 * @property {string}      startTime    - ISO datetime range start.
 * @property {string}      endTime      - ISO datetime range end.
 * @property {0|1}         signType     - 0 = pending, 1 = signed.
 * @property {string}      dateMode     - "assignment" | "arrival".
 * @property {string}      target_staff - Exact staff name to filter by.
 * @property {string|null} target_date  - ISO date (YYYY-MM-DD) or null for "all dates".
 */

/**
 * Fetches the full staff × date matrix for the Pending Dashboard.
 *
 * Endpoint: POST /api/network/waybills
 * Response contract: { summary: DashboardSummaryDTO, rows: DashboardRowDTO[], dates: string[] }
 *
 * @param {string} networkCode
 * @param {string} start       - Formatted start datetime string.
 * @param {string} end         - Formatted end datetime string.
 * @param {string} dateMode    - "assignment" | "arrival"
 * @returns {Promise<{summary: object, rows: object[], dates: string[]}>}
 */
export function fetchPendingWaybills(networkCode, start, end, dateMode) {
    /** @type {DashboardMatrixPayload} */
    const payload = {
        networkCode,
        startTime: start,
        endTime: end,
        signType: 0,
        dateMode,
    };
    return post('/api/network/waybills', payload);
}

/**
 * Fetches the individual waybill records for a single cell in the dashboard matrix.
 * Uses the dedicated details endpoint that returns a flat List[WaybillDTO] —
 * no matrix unwrapping required on the frontend.
 *
 * Endpoint: POST /api/network/waybills/details
 * Response contract: WaybillDTO[]  (flat array)
 *
 * @param {string}      networkCode
 * @param {string}      start       - Formatted start datetime string.
 * @param {string}      end         - Formatted end datetime string.
 * @param {string}      staff       - Exact staff name (matches DashboardRowDTO.staff).
 * @param {string}      date        - ISO date "YYYY-MM-DD", or "ALL" to retrieve all dates.
 * @param {string}      dateMode    - "assignment" | "arrival"
 * @returns {Promise<object[]>}
 */
export function fetchCellDetails(networkCode, start, end, staff, date, dateMode) {
    /** @type {CellDetailPayload} */
    const payload = {
        networkCode,
        startTime: start,
        endTime: end,
        signType: 0,
        dateMode,
        target_staff: staff,
        target_date: date === 'ALL' ? null : date,
    };
    return post('/api/network/waybills/details', payload);
}
