import { html, useState } from '../../lib/ui.js';
import { reprintWaybills } from '../../services/settlementService.js';

function parseWaybills(rawValue) {
    return String(rawValue || '')
        .split(/[\n,\s]+/)
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean);
}

function isCompleteWaybill(value) {
    const normalized = String(value || '').trim().toUpperCase();
    return /^[A-Z]{2,5}\d{8,}$/.test(normalized);
}

export default function FloatingReprintButton() {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState('');
    const [waybillItems, setWaybillItems] = useState([]);
    const [loadingWaybill, setLoadingWaybill] = useState('');
    const [bulkLoading, setBulkLoading] = useState(false);
    const [error, setError] = useState('');

    const openPanel = () => {
        setIsOpen(true);
        setError('');
    };

    const closePanel = () => {
        setIsOpen(false);
        setError('');
    };

    const openPdf = (pdfUrl) => {
        const popup = window.open(pdfUrl, '_blank', 'noopener,noreferrer');
        if (!popup) {
            window.location.href = pdfUrl;
        }
    };

    const mergeWaybills = (incoming) => {
        if (!incoming.length) return;
        setWaybillItems((prev) => {
            const existing = new Set(prev);
            const merged = [...prev];
            incoming.forEach((item) => {
                if (!existing.has(item)) {
                    merged.push(item);
                    existing.add(item);
                }
            });
            return merged;
        });
    };

    const addWaybills = (rawValue, { clearInput = true } = {}) => {
        const parsed = parseWaybills(rawValue);

        if (!parsed.length) {
            setError('Ingresa al menos una guía válida.');
            return;
        }

        mergeWaybills(parsed);
        if (clearInput) setInputValue('');
        setError('');
    };

    const handleInputChange = (event) => {
        const raw = event.target.value.toUpperCase();
        setInputValue(raw);
        setError('');

        if (/[\n,]/.test(raw)) {
            addWaybills(raw);
            return;
        }

        const trimmed = raw.trim();
        if (trimmed && isCompleteWaybill(trimmed)) {
            addWaybills(trimmed);
        }
    };

    const removeWaybill = (waybill) => {
        setWaybillItems((prev) => prev.filter((item) => item !== waybill));
    };

    const handleReprintOne = async (waybill) => {
        const waybillIds = [waybill];

        setLoadingWaybill(waybill);
        setError('');
        try {
            const response = await reprintWaybills(waybillIds, 'small');
            const pdfUrl = response?.data?.pdf_url;
            if (!pdfUrl) {
                throw new Error('No se recibió URL de reimpresión.');
            }

            openPdf(pdfUrl);
        } catch (err) {
            setError(err.message || 'No se pudo generar la reimpresión.');
        } finally {
            setLoadingWaybill('');
        }
    };

    const handleReprintAll = async () => {
        const waybillIds = waybillItems;

        if (!waybillIds.length) {
            setError('Agrega al menos una guía para reimprimir.');
            return;
        }

        setBulkLoading(true);
        setError('');
        try {
            const response = await reprintWaybills(waybillIds, 'small');
            const pdfUrl = response?.data?.pdf_url;
            if (!pdfUrl) {
                throw new Error('No se recibió URL de reimpresión.');
            }

            openPdf(pdfUrl);
        } catch (err) {
            setError(err.message || 'No se pudo generar la reimpresión.');
        } finally {
            setBulkLoading(false);
        }
    };

    return html`
        <div className="floating-reprint-wrapper no-print">
            <button
                type="button"
                className="floating-reprint-btn"
                title="Reimprimir guía(s)"
                onClick=${openPanel}
            >
                🖨️
            </button>

            ${isOpen
                ? html`
                    <div className="reprint-overlay" onClick=${closePanel}>
                        <div className="reprint-window" onClick=${(e) => e.stopPropagation()}>
                            <header>
                                <h4>Reimprimir guía(s)</h4>
                                <button type="button" className="barcode-close" onClick=${closePanel}>Cerrar ✕</button>
                            </header>

                            <div className="reprint-input-row">
                                <textarea
                                    className="reprint-textarea"
                                    placeholder="Pega o escribe guías; se detectan automáticamente"
                                    value=${inputValue}
                                    onChange=${handleInputChange}
                                ></textarea>
                            </div>

                            <div className="reprint-cards">
                                ${waybillItems.length
            ? waybillItems.map((waybill) => html`
                                        <div className="reprint-card" key=${waybill}>
                                            <span className="reprint-code">${waybill}</span>
                                            <div className="reprint-card-actions">
                                                <button
                                                    type="button"
                                                    className="reprint-btn"
                                                    onClick=${() => handleReprintOne(waybill)}
                                                    disabled=${bulkLoading || loadingWaybill === waybill}
                                                >
                                                    ${loadingWaybill === waybill ? 'Generando…' : 'Reimprimir'}
                                                </button>
                                                <button
                                                    type="button"
                                                    className="reprint-btn reprint-btn-danger"
                                                    onClick=${() => removeWaybill(waybill)}
                                                    disabled=${bulkLoading || loadingWaybill === waybill}
                                                >
                                                    Quitar
                                                </button>
                                            </div>
                                        </div>
                                    `)
            : html`<p className="barcode-empty">Sin guías agregadas.</p>`}
                            </div>

                            ${error ? html`<p className="barcode-error">${error}</p>` : null}

                            <div className="modal-actions">
                                <button type="button" className="reprint-btn" onClick=${closePanel}>Cancelar</button>
                                <button type="button" className="reprint-btn reprint-btn-primary" onClick=${handleReprintAll} disabled=${bulkLoading || !waybillItems.length}>
                                    ${bulkLoading ? 'Generando…' : 'Reimprimir todas'}
                                </button>
                            </div>
                        </div>
                    </div>
                `
                : null}
        </div>
    `;
}
