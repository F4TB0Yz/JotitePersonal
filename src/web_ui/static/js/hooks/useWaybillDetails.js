import { useState, useEffect } from '../lib/ui.js';
import { fetchWaybillDetails, fetchWaybillPhones } from '../services/addressService.js';
import { fetchMessengerContact } from '../services/messengerService.js';

/**
 * @typedef {Object} PhoneEntry
 * @property {string}  value   - The phone number, or '' if not yet loaded.
 * @property {boolean} visible - Whether to show the value in the UI.
 * @property {boolean} loading - Whether a fetch is in progress.
 * @property {string}  error   - Error message, or '' if none.
 */

/**
 * @typedef {Object} WaybillDetailsState
 * @property {Record<string, object>} detailMap         - Map of waybillNo → enriched detail object.
 * @property {boolean}                detailLoading     - True while fetching waybill details.
 * @property {string}                 detailError       - Error message from detail fetch, or ''.
 * @property {Record<string, PhoneEntry>} phoneState    - Per-waybill phone reveal state.
 * @property {Record<string, PhoneEntry>} messengerContacts - Per-staff phone reveal state.
 * @property {(waybillNo: string) => void} handlePhoneClick   - Toggles/fetches phone for a waybill.
 * @property {(staff: string, networkCode: string, sampleWaybill: string) => void} handleMessengerClick - Toggles/fetches messenger contact.
 */

/**
 * Manages all detail, phone, and messenger-contact state for the Pending Dashboard.
 * Extracts these concerns from PendingDashboardView so the view remains a pure
 * presentation component.
 *
 * @param {{ selectedCell: object|null, networkCode: string, getSampleWaybillForStaff: (staff: string) => string }} params
 * @returns {WaybillDetailsState}
 */
export function useWaybillDetails({ selectedCell, networkCode, getSampleWaybillForStaff }) {
    const [detailMap, setDetailMap] = useState({});
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState('');
    const [phoneState, setPhoneState] = useState({});
    const [messengerContacts, setMessengerContacts] = useState({});

    // ── Reset on network change ───────────────────────────────────────────────
    useEffect(() => {
        setMessengerContacts({});
    }, [networkCode]);

    // ── Fetch waybill details when selected cell changes ─────────────────────
    useEffect(() => {
        if (!selectedCell?.records) {
            setDetailMap({});
            setDetailError('');
            setDetailLoading(false);
            setPhoneState({});
            return;
        }

        const ids = _extractUniqueWaybillIds(selectedCell.records);

        if (ids.length === 0) {
            setDetailMap({});
            setDetailLoading(false);
            return;
        }

        let cancelled = false;
        setDetailLoading(true);
        setDetailError('');

        fetchWaybillDetails(ids)
            .then((data) => { if (!cancelled) setDetailMap(data || {}); })
            .catch((err) => {
                if (cancelled) return;
                setDetailError(err?.message || 'No se pudo obtener el detalle de las guías.');
                setDetailMap({});
            })
            .finally(() => { if (!cancelled) setDetailLoading(false); });

        return () => { cancelled = true; };
    }, [selectedCell]);

    // ── Prune phone state to only visible waybills ────────────────────────────
    useEffect(() => {
        if (!selectedCell?.records) return;
        const allowed = new Set(_extractUniqueWaybillIds(selectedCell.records));
        setPhoneState((prev) => {
            const next = {};
            allowed.forEach((wb) => { if (prev[wb]) next[wb] = prev[wb]; });
            return next;
        });
    }, [selectedCell]);

    // ── Public handlers ───────────────────────────────────────────────────────

    /**
     * Reveals or fetches the phone number for a given waybill.
     * @param {string} waybillNo
     */
    function handlePhoneClick(waybillNo) {
        if (!waybillNo) return;
        const current = phoneState[waybillNo];

        if (current?.value && !current.loading) {
            setPhoneState((prev) => ({
                ...prev,
                [waybillNo]: { ...current, visible: !current.visible },
            }));
            return;
        }

        setPhoneState((prev) => ({
            ...prev,
            [waybillNo]: { value: '', visible: true, loading: true, error: '' },
        }));

        fetchWaybillPhones([waybillNo])
            .then((data) => {
                const phone = data?.[waybillNo];
                setPhoneState((prev) => ({
                    ...prev,
                    [waybillNo]: {
                        value: phone || '',
                        visible: Boolean(phone),
                        loading: false,
                        error: phone ? '' : 'Teléfono no disponible',
                    },
                }));
            })
            .catch((err) => {
                setPhoneState((prev) => ({
                    ...prev,
                    [waybillNo]: {
                        value: '',
                        visible: false,
                        loading: false,
                        error: err?.message || 'Error consultando teléfono',
                    },
                }));
            });
    }

    /**
     * Reveals or fetches the contact phone for a messenger (staff member).
     * @param {string} staff
     */
    function handleMessengerClick(staff) {
        if (!staff || staff === 'Sin enrutar') return;
        const key = staff.trim().toLowerCase();
        const current = messengerContacts[key];

        if (current?.value && !current.loading) {
            setMessengerContacts((prev) => ({
                ...prev,
                [key]: { ...current, visible: !current.visible },
            }));
            return;
        }

        setMessengerContacts((prev) => ({
            ...prev,
            [key]: { value: '', loading: true, visible: false, error: '' },
        }));

        const sampleWaybill = getSampleWaybillForStaff(staff);
        fetchMessengerContact(staff, networkCode, sampleWaybill)
            .then((data) => {
                const phone = data?.phone;
                setMessengerContacts((prev) => ({
                    ...prev,
                    [key]: {
                        value: phone || '',
                        loading: false,
                        visible: Boolean(phone),
                        error: phone ? '' : 'Teléfono no disponible',
                    },
                }));
            })
            .catch((err) => {
                setMessengerContacts((prev) => ({
                    ...prev,
                    [key]: { value: '', loading: false, visible: false, error: err?.message || 'Error consultando mensajero' },
                }));
            });
    }

    return {
        detailMap,
        detailLoading,
        detailError,
        phoneState,
        messengerContacts,
        handlePhoneClick,
        handleMessengerClick,
    };
}

// ── Private helpers ───────────────────────────────────────────────────────────

/**
 * Extracts a deduplicated list of valid waybill IDs from a records array.
 * @param {object[]} records
 * @returns {string[]}
 */
function _extractUniqueWaybillIds(records) {
    return Array.from(
        new Set(
            records
                .map((item) => item.waybillNo)
                .filter((wb) => typeof wb === 'string' && wb.trim().length > 0)
        )
    );
}
