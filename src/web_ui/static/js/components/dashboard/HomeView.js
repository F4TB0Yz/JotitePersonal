import { html } from '../../lib/ui.js';

export default function HomeView() {
    return html`
        <div className="home-view">
            <div className="home-hero">
                <div className="home-hero-logo">
                    <span className="home-hero-jt">J&T</span>
                    <span className="home-hero-express">Express</span>
                </div>
                <p className="home-hero-sub">Panel de herramientas</p>
            </div>

            <div className="home-tools-grid">
                <div className="home-tool-card">
                    <span className="home-tool-icon">🖨️</span>
                    <p className="home-tool-label">Reimprimir etiqueta</p>
                </div>
                <div className="home-tool-card">
                    <span className="home-tool-icon">📷</span>
                    <p className="home-tool-label">Escáner código</p>
                </div>
                <div className="home-tool-card">
                    <span className="home-tool-icon">📞</span>
                    <p className="home-tool-label">Teléfono mensajero</p>
                </div>
                <div className="home-tool-card">
                    <span className="home-tool-icon">💬</span>
                    <p className="home-tool-label">Plantillas mensaje</p>
                </div>
                <div className="home-tool-card home-tool-card--highlight">
                    <span className="home-tool-icon">📋</span>
                    <p className="home-tool-label">Reporte diario</p>
                </div>
            </div>

            <p className="home-hint">Usa los botones flotantes para acceder a cada herramienta</p>
        </div>
    `;
}
