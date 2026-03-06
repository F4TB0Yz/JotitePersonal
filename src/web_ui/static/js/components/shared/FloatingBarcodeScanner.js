import { html, useState, useEffect, useRef } from '../../lib/ui.js';

function QuickBarcodeSlide({ value }) {
    const svgRef = useRef(null);

    useEffect(() => {
        if (window.JsBarcode && svgRef.current && value) {
            try {
                window.JsBarcode(svgRef.current, value, {
                    format: 'code128',
                    lineColor: '#111111',
                    background: '#ffffff',
                    displayValue: false,
                    margin: 0,
                    height: 140,
                    width: 2
                });
            } catch (err) {
                console.error('Barcode render error', err);
            }
        }
    }, [value]);

    if (!value) {
        return html`<p className="barcode-empty">Ingresa una guía y genera el código.</p>`;
    }

    return html`
        <div className="barcode-slide quick">
            <svg ref=${svgRef} className="barcode-svg" role="img" aria-label=${`Código ${value}`}></svg>
            <p className="barcode-value">${value}</p>
        </div>
    `;
}

export default function FloatingBarcodeScanner() {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState('');
    const [currentValue, setCurrentValue] = useState('');
    const [error, setError] = useState('');

    const handleOpen = () => {
        setIsOpen(true);
        setError('');
    };

    const handleClose = () => {
        setIsOpen(false);
        setError('');
    };

    const handleGenerate = () => {
        const trimmed = (inputValue || '').trim().toUpperCase();
        if (!trimmed) {
            setError('Ingresa un número de guía');
            setCurrentValue('');
            return;
        }
        setError('');
        setCurrentValue(trimmed);
    };

    return html`
        <div className="floating-barcode-wrapper">
            <button
                type="button"
                className="floating-barcode-btn"
                title="Generar código de barras de guía"
                onClick=${handleOpen}
            >
                🧾
            </button>

            ${isOpen
                ? html`
                    <div className="barcode-overlay" onClick=${handleClose}>
                        <div className="barcode-window quick" onClick=${(e) => e.stopPropagation()}>
                            <header>
                                <div>
                                    <p>Generador rápido</p>
                                    <h4>Código de barras de guía</h4>
                                </div>
                                <button type="button" className="barcode-close" onClick=${handleClose}>
                                    Cerrar ✕
                                </button>
                            </header>

                            <div className="floating-barcode-body">
                                <div className="floating-barcode-input-row">
                                    <input
                                        type="text"
                                        className="form-input"
                                        placeholder="Ingresa número de guía..."
                                        value=${inputValue}
                                        onChange=${(e) => setInputValue(e.target.value)}
                                        onKeyPress=${(e) => {
                                            if (e.key === 'Enter') handleGenerate();
                                        }}
                                    />
                                    <button type="button" className="form-btn primary" onClick=${handleGenerate}>
                                        Generar
                                    </button>
                                </div>
                                ${error ? html`<p className="barcode-error">${error}</p>` : null}

                                <div className="barcode-carousel quick">
                                    <${QuickBarcodeSlide} value=${currentValue} />
                                </div>
                            </div>
                        </div>
                    </div>`
                : null}
        </div>
    `;
}
