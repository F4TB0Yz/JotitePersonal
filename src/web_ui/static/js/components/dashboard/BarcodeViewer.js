import { html, useEffect, useRef } from '../../lib/ui.js';
import { formatDateTimeLabel } from '../../utils/formatters.js';

function BarcodeSlide({ value, goods, weight, staff, operateTime }) {
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

    return html`
        <div className="barcode-slide">
            <div className="barcode-metadata">
                <p>${goods || 'Contenido no disponible'}</p>
                <p>${weight ? `${weight} kg` : ''}</p>
            </div>
            <svg ref=${svgRef} className="barcode-svg" role="img" aria-label=${`Código ${value}`}></svg>
            <p className="barcode-value">${value}</p>
            <div className="barcode-meta-foot">
                <span>${staff || 'Sin operador'}</span>
                <span>${formatDateTimeLabel(operateTime)}</span>
            </div>
        </div>
    `;
}

export default function BarcodeModal({ items, index, onClose, onPrev, onNext, festivo = false }) {
    const current = items[index];
    return html`
        <div className="barcode-overlay" onClick=${onClose}>
            <div className="barcode-window" onClick=${(event) => event.stopPropagation()}>
                <header>
                    <div>
                        <p>
                            Modo escáner
                            ${festivo ? html`<span className="barcode-festivo-badge">🎉 Modo Festivo</span>` : null}
                        </p>
                        <h4>${current?.value || 'Sin datos'}</h4>
                    </div>
                    <button type="button" className="barcode-close" onClick=${onClose}>Cerrar ✕</button>
                </header>
                <div className="barcode-carousel">
                    ${current
                        ? html`<${BarcodeSlide}
                            value=${current.value}
                            goods=${current.goods}
                            weight=${current.weight}
                            staff=${current.staff}
                            operateTime=${current.operateTime}
                        />`
                        : html`<p className="barcode-empty">Sin guías para mostrar.</p>`}
                </div>
                <footer>
                    <button type="button" className="barcode-nav" onClick=${onPrev} disabled=${items.length <= 1}>
                        ◀
                    </button>
                    <span>${items.length ? `${index + 1} / ${items.length}` : '0 / 0'}</span>
                    <button type="button" className="barcode-nav" onClick=${onNext} disabled=${items.length <= 1}>
                        ▶
                    </button>
                </footer>
            </div>
        </div>
    `;
}
