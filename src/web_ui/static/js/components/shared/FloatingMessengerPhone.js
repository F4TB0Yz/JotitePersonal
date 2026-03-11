import { html, useState } from '../../lib/ui.js';
import { searchMessengers, fetchMessengerContact } from '../../services/messengerService.js';

export default function FloatingMessengerPhone() {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState('');
    const [suggestions, setSuggestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [phone, setPhone] = useState('');
    const [messengerName, setMessengerName] = useState('');
    const [error, setError] = useState('');
    const [searchTimer, setSearchTimer] = useState(null);

    const openPanel = () => {
        setIsOpen(true);
        setError('');
    };

    const closePanel = () => {
        setIsOpen(false);
        setError('');
        setPhone('');
        setMessengerName('');
        setSuggestions([]);
        setInputValue('');
    };

    const handleInputChange = (e) => {
        const value = e.target.value;
        setInputValue(value);
        setPhone('');
        setMessengerName('');
        setError('');

        if (searchTimer) clearTimeout(searchTimer);

        if (!value || value.trim().length < 2) {
            setSuggestions([]);
            return;
        }

        const timer = setTimeout(() => {
            searchMessengers(value)
                .then((results) => setSuggestions(results || []))
                .catch(() => setSuggestions([]));
        }, 300);
        setSearchTimer(timer);
    };

    const handleSelectMessenger = async (messenger) => {
        setSuggestions([]);
        setInputValue(messenger.accountName);
        setLoading(true);
        setError('');
        setPhone('');
        setMessengerName(messenger.accountName);

        try {
            const data = await fetchMessengerContact(
                messenger.accountName,
                messenger.customerNetworkCode || ''
            );
            if (data?.phone) {
                setPhone(data.phone);
            } else {
                setError('No se encontró teléfono para este mensajero.');
            }
        } catch {
            setError('No se pudo consultar el teléfono.');
        } finally {
            setLoading(false);
        }
    };

    return html`
        <div className="floating-messenger-phone-wrapper no-print">
            <button
                type="button"
                className="floating-messenger-phone-btn"
                title="Buscar teléfono de mensajero"
                onClick=${openPanel}
            >
                🛵
            </button>

            ${isOpen
                ? html`
                    <div className="barcode-overlay" onClick=${closePanel}>
                        <div className="barcode-window quick" onClick=${(e) => e.stopPropagation()}>
                            <header>
                                <div>
                                    <p>Consulta rápida</p>
                                    <h4>Teléfono de mensajero</h4>
                                </div>
                                <button type="button" className="barcode-close" onClick=${closePanel}>Cerrar ✕</button>
                            </header>

                            <div className="floating-phone-body">
                                <div className="floating-messenger-search-container">
                                    <input
                                        type="text"
                                        className="form-input"
                                        placeholder="Nombre del mensajero..."
                                        value=${inputValue}
                                        onInput=${handleInputChange}
                                        autoComplete="off"
                                    />
                                    ${suggestions.length > 0
                                        ? html`<ul className="floating-messenger-suggestions">
                                            ${suggestions.map((m) => html`
                                                <li key=${m.accountCode} onMouseDown=${() => handleSelectMessenger(m)}>
                                                    <strong>${m.accountName}</strong>
                                                    <span>${m.accountCode} · ${m.customerNetworkName || 'Sin punto'}</span>
                                                </li>
                                            `)}
                                        </ul>`
                                        : null}
                                </div>

                                ${loading ? html`<p className="floating-phone-result">Buscando…</p>` : null}
                                ${phone
                                    ? html`<div className="floating-messenger-result">
                                        <p><strong>${messengerName}</strong></p>
                                        <p className="floating-messenger-phone-number">
                                            <a href="tel:${phone}">${phone}</a>
                                        </p>
                                    </div>`
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
