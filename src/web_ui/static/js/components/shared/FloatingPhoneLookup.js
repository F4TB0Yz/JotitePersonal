import { html, useState } from '../../lib/ui.js';
import { fetchWaybillPhones } from '../../services/addressService.js';

export default function FloatingPhoneLookup() {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState('');
    const [loading, setLoading] = useState(false);
    const [phone, setPhone] = useState('');
    const [error, setError] = useState('');

    const openPanel = () => {
        setIsOpen(true);
        setError('');
    };

    const closePanel = () => {
        setIsOpen(false);
        setError('');
    };

    const handleLookup = async () => {
        const waybill = String(inputValue || '').trim().toUpperCase();
        if (!waybill) {
            setError('Ingresa una guía válida.');
            setPhone('');
            return;
        }

        setLoading(true);
        setError('');
        setPhone('');

        try {
            const response = await fetchWaybillPhones([waybill]);
            const foundPhone = response?.[waybill];

            if (!foundPhone) {
                setError('No se encontró teléfono para esta guía.');
                return;
            }

            setPhone(foundPhone);
        } catch (err) {
            setError(err.message || 'No se pudo consultar el teléfono.');
        } finally {
            setLoading(false);
        }
    };

    return html`
        <div className="floating-phone-wrapper no-print">
            <button
                type="button"
                className="floating-phone-btn"
                title="Consultar teléfono de guía"
                onClick=${openPanel}
            >
                📞
            </button>

            ${isOpen
                ? html`
                    <div className="barcode-overlay" onClick=${closePanel}>
                        <div className="barcode-window quick" onClick=${(e) => e.stopPropagation()}>
                            <header>
                                <div>
                                    <p>Consulta rápida</p>
                                    <h4>Teléfono por guía</h4>
                                </div>
                                <button type="button" className="barcode-close" onClick=${closePanel}>Cerrar ✕</button>
                            </header>

                            <div className="floating-phone-body">
                                <div className="floating-phone-input-row">
                                    <input
                                        type="text"
                                        className="form-input"
                                        placeholder="Ingresa número de guía..."
                                        value=${inputValue}
                                        onChange=${(e) => setInputValue(e.target.value)}
                                        onKeyPress=${(e) => {
                                            if (e.key === 'Enter') handleLookup();
                                        }}
                                    />
                                    <button type="button" className="form-btn primary" onClick=${handleLookup} disabled=${loading}>
                                        ${loading ? 'Buscando…' : 'Buscar'}
                                    </button>
                                </div>

                                ${phone
                                    ? html`<p className="floating-phone-result">Teléfono: <strong>${phone}</strong></p>`
                                    : null}
                                ${error ? html`<p className="barcode-error">${error}</p>` : null}
                            </div>
                        </div>
                    </div>
                `
                : null}
        </div>
    `;
}
