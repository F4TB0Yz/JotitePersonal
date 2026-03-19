import { html, useState, useEffect, useRef } from '../../lib/ui.js';
import { fetchWaybillTimeline } from '../../services/timelineService.js';
import { fetchWaybillPhotos, getPhotosDownloadUrl, getPhotoProxyDownloadUrl } from '../../services/photosService.js';
import WaybillTimeline from './WaybillTimeline.js';

export default function WaybillQueryModal() {
    const [isOpen, setIsOpen] = useState(false);
    const [waybillInput, setWaybillInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [timeline, setTimeline] = useState([]);
    const [timelineLoading, setTimelineLoading] = useState(false);
    const [timelineError, setTimelineError] = useState('');
    const [photos, setPhotos] = useState([]);
    const [photosLoading, setPhotosLoading] = useState(false);
    const [photosError, setPhotosError] = useState('');
    const [lightbox, setLightbox] = useState({ open: false, index: 0 });
    const [downloadName, setDownloadName] = useState('JTC0000');
    const socketRef = useRef(null);

    useEffect(() => {
        if (typeof window === 'undefined') return;

        const handleOpen = (e) => {
            setIsOpen(true);
            if (e.detail && e.detail.waybill) {
                setWaybillInput(e.detail.waybill);
                handleSearch(e.detail.waybill);
            }
        };

        window.addEventListener('open-query-modal', handleOpen);
        return () => {
            window.removeEventListener('open-query-modal', handleOpen);
            if (socketRef.current) socketRef.current.close();
        };
    }, []);

    useEffect(() => {
        if (typeof document === 'undefined' || typeof window === 'undefined') return;
        if (result && result.waybill_no) {
            setTimeout(() => {
                const btn = document.getElementById(`novedad-btn-${result.waybill_no}`);
                if (btn) {
                    btn.onclick = () => {
                        window.dispatchEvent(new CustomEvent('open-novedades-modal', { 
                            detail: { waybill: result.waybill_no } 
                        }));
                    };
                }
            }, 0);
        }
    }, [result]);

    useEffect(() => {
        const waybillNo = result?.waybill_no;
        if (!waybillNo) {
            setTimeline([]);
            setTimelineError('');
            setTimelineLoading(false);
            return;
        }

        setTimelineLoading(true);
        setTimelineError('');
        fetchWaybillTimeline(waybillNo)
            .then((payload) => {
                setTimeline(payload?.events || []);
            })
            .catch((err) => {
                setTimeline([]);
                setTimelineError(err?.message || 'No se pudo cargar el timeline.');
            })
            .finally(() => setTimelineLoading(false));
    }, [result?.waybill_no]);

    useEffect(() => {
        setDownloadName('JTC0000');
        setLightbox({ open: false, index: 0 });
    }, [result?.waybill_no]);

    useEffect(() => {
        const waybillNo = result?.waybill_no;
        if (!waybillNo || !result?.is_delivered) {
            setPhotos([]);
            setPhotosError('');
            setPhotosLoading(false);
            return;
        }

        setPhotosLoading(true);
        setPhotosError('');
        fetchWaybillPhotos(waybillNo)
            .then((payload) => {
                setPhotos(payload?.photos || []);
                if (payload?.error) setPhotosError(payload.error);
            })
            .catch((err) => {
                setPhotos([]);
                setPhotosError(err?.message || 'No se pudieron cargar las fotos.');
            })
            .finally(() => setPhotosLoading(false));
    }, [result?.waybill_no, result?.is_delivered]);

    const handleSearch = (targetWaybill = waybillInput) => {
        try {
            const wb = targetWaybill.trim().toUpperCase();
            if (!wb) return;

            setLoading(true);
            setError(null);
            setResult(null);
            setTimeline([]);
            setTimelineError('');
            setTimelineLoading(false);
            setPhotos([]);
            setPhotosError('');
            setPhotosLoading(false);

            // Usamos el WebSocket de procesamiento para consultar la guia individualmente
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/process`;
            
            if (socketRef.current) socketRef.current.close();
            
            let retried = false;

            function connectWs() {
                socketRef.current = new WebSocket(wsUrl);

                socketRef.current.onopen = () => {
                    try {
                        socketRef.current.send(JSON.stringify({ waybills: [wb] }));
                    } catch (sendErr) {
                        console.error('Error enviando petición de guía:', sendErr);
                        setError('Error al enviar la consulta de la guía');
                        setLoading(false);
                    }
                };

                socketRef.current.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        console.log("WS Query received:", data);
                        if (data.type === 'result') {
                            // Normalizar el resultado para evitar errores de renderizado
                            let normalizedResult = null;
                            if (data.results && Array.isArray(data.results) && data.results.length > 0) {
                                normalizedResult = data.results[0];
                            } else if (data.result_dict) {
                                normalizedResult = data.result_dict;
                            } else if (data.data) {
                                normalizedResult = data.data;
                            }

                            if (normalizedResult) {
                                setResult(normalizedResult);
                            } else {
                                console.warn('Formato inesperado de respuesta WS (sin datos utilizables):', data);
                                setError("No se encontraron datos para esta guía");
                            }
                            setLoading(false);
                            if (socketRef.current) {
                                socketRef.current.close();
                                socketRef.current = null;
                            }
                        } else if (data.type === 'error') {
                            setError(data.message || 'Error en la consulta de la guía');
                            setLoading(false);
                            if (socketRef.current) {
                                socketRef.current.close();
                                socketRef.current = null;
                            }
                        } else if (data.type === 'done') {
                            if (!result) {
                                setError('No se encontraron datos para esta guía');
                            }
                            setLoading(false);
                            if (socketRef.current) {
                                socketRef.current.close();
                                socketRef.current = null;
                            }
                        } else {
                            console.warn('Tipo de mensaje WS no manejado en consulta de guía:', data);
                        }
                    } catch (err) {
                        console.error("Error parsing WS message:", err);
                        setError("Error al procesar la respuesta del servidor");
                        setLoading(false);
                    }
                };

                socketRef.current.onerror = (err) => {
                    console.error("WS Socket Error:", err);
                    if (!retried) {
                        retried = true;
                        socketRef.current = null;
                        setTimeout(connectWs, 2000);
                        return;
                    }
                    setError("Error de conexión con el servidor");
                    setLoading(false);
                    if (socketRef.current) {
                        socketRef.current.close();
                        socketRef.current = null;
                    }
                };

                socketRef.current.onclose = () => {
                    if (loading) {
                        if (!retried) {
                            retried = true;
                            socketRef.current = null;
                            setTimeout(connectWs, 2000);
                            return;
                        }
                        setError('La conexión se cerró sin resultados.');
                        setLoading(false);
                    }
                    socketRef.current = null;
                };
            }

            connectWs();
        } catch (err) {
            console.error('Error iniciando consulta de guía:', err);
            setError('Error al iniciar la consulta de la guía');
            setLoading(false);
        }
    };

    const handleClose = () => {
        setIsOpen(false);
        setWaybillInput('');
        setResult(null);
        setError(null);
        setTimeline([]);
        setTimelineError('');
        setTimelineLoading(false);
        setPhotos([]);
        setPhotosError('');
        setPhotosLoading(false);
        setLightbox({ open: false, index: 0 });
        setDownloadName('JTC0000');
        if (socketRef.current) {
            socketRef.current.close();
            socketRef.current = null;
        }
    };

    if (!isOpen) return null;

    const showResult = result && !loading;
    const showLoading = loading && !result;
    const wb = result?.waybill_no || 'N/A';
    const badgeClass = result?.is_delivered ? 'delivered' : 'pending';
    const badgeText = result?.is_delivered ? 'ENTREGADO' : 'PENDIENTE';

    return html`
        <div className="query-modal-overlay ${isOpen ? 'active' : ''}" onClick=${(e) => {
            if (e.target.classList.contains('query-modal-overlay')) handleClose();
        }}>
            <div className="query-modal-content">
                <div className="query-modal-header">
                    <h3>🔍 Consulta de Guía Express</h3>
                    <button className="close-btn" onClick=${handleClose}>×</button>
                </div>

                <div className="query-modal-body">
                    <div className="query-search-box">
                        <input 
                            type="text" 
                            className="form-input" 
                            placeholder="Ingrese número de guía..."
                            value=${waybillInput}
                            onChange=${(e) => setWaybillInput(e.target.value)}
                            onKeyPress=${(e) => e.key === 'Enter' && handleSearch()}
                        />
                        <button className="form-btn primary" onClick=${() => handleSearch()} disabled=${loading}>
                            ${loading ? 'Consultando...' : 'Consultar'}
                        </button>
                    </div>

                    ${error ? html`<div className="query-error">⚠️ ${error}</div>` : null}

                    ${showResult ? html`
                        <div className="query-result-card animate-in">
                            <div className="res-header">
                                <span className="res-number">${wb}</span>
                                <span className="res-status-badge ${badgeClass}">${badgeText}</span>
                            </div>
                            
                            <div className="res-info-grid">
                                <div className="info-item">
                                    <label>Destinatario</label>
                                    <p>${result.receiver || 'N/A'}</p>
                                </div>
                                <div className="info-item">
                                    <label>Ciudad</label>
                                    <p>${result.city || 'N/A'}</p>
                                </div>
                                <div className="info-item full">
                                    <label>Dirección</label>
                                    <p>${result.address || 'N/A'}</p>
                                </div>
                                <div className="info-item">
                                    <label>Último Estado</label>
                                    <p>${result.status || 'N/A'}</p>
                                </div>
                                <div className="info-item">
                                    <label>Último Evento</label>
                                    <p>${result.last_event_time || 'N/A'}</p>
                                </div>
                                <div className="info-item">
                                    <label>Mensajero</label>
                                    <p>${result.last_staff || 'Sin asignar'} ${result.staff_contact ? '📞 ' + result.staff_contact : ''}</p>
                                </div>
                                <div className="info-item">
                                    <label>Arribo Punto 6</label>
                                    <p>${result.arrival_punto6_time || 'No ha llegado'}</p>
                                </div>
                            </div>

                            ${result.exceptions ? html`
                                <div className="res-exceptions">
                                    <label>⚠️ Novedades de Campo:</label>
                                    <p>${result.exceptions}</p>
                                </div>
                            ` : null}

                            ${result.is_delivered ? html`
                                <section className="delivery-photos-section">
                                    <div className="delivery-photos-header">
                                        <h4>📸 Fotos de entrega</h4>
                                        ${photos.length > 0 ? html`
                                            <a
                                                href=${getPhotosDownloadUrl(result.waybill_no)}
                                                download
                                                className="form-btn secondary photos-download-btn"
                                            >⬇ Descargar ZIP</a>
                                        ` : null}
                                    </div>
                                    ${photosLoading ? html`<p className="photos-state">Cargando fotos...</p>` : null}
                                    ${photosError && !photosLoading ? html`<p className="photos-state error">${photosError}</p>` : null}
                                    ${!photosLoading && photos.length > 0 ? html`
                                        <div className="photos-grid">
                                            ${photos.map((url, i) => html`
                                                <div key=${i} className="photo-thumb-link" onClick=${() => setLightbox({ open: true, index: i })}>
                                                    <img src=${getPhotoProxyDownloadUrl(url)} alt=${'Foto ' + (i + 1)} className="photo-thumb" loading="lazy" />
                                                </div>
                                            `)}
                                        </div>
                                    ` : null}
                                    ${!photosLoading && !photosError && photos.length === 0 ? html`<p className="photos-state">Sin fotos disponibles.</p>` : null}
                                </section>
                            ` : null}

                            <${WaybillTimeline}
                                events=${timeline}
                                loading=${timelineLoading}
                                error=${timelineError}
                            />
                        </div>
                    ` : null}

                    ${showLoading ? html`
                        <div className="query-loading">
                            <div className="spinner"></div>
                            <p>Interrogando APIs de J&T Express...</p>
                        </div>
                    ` : null}
                </div>
            </div>
        </div>

        ${lightbox.open && photos.length > 0 ? html`
            <div className="photo-lightbox-overlay" onClick=${() => setLightbox((prev) => ({ ...prev, open: false }))}>
                <div className="photo-lightbox-box" onClick=${(e) => e.stopPropagation()}>
                    <button className="lightbox-close" onClick=${() => setLightbox((prev) => ({ ...prev, open: false }))}>×</button>
                    <img
                        src=${getPhotoProxyDownloadUrl(photos[lightbox.index])}
                        alt=${'Foto ' + (lightbox.index + 1)}
                        className="lightbox-img"
                    />
                    <div className="lightbox-controls">
                        <button
                            className="lightbox-nav"
                            disabled=${lightbox.index === 0}
                            onClick=${() => setLightbox((prev) => ({ ...prev, index: prev.index - 1 }))}
                        >‹</button>
                        <span className="lightbox-counter">${lightbox.index + 1} / ${photos.length}</span>
                        <button
                            className="lightbox-nav"
                            disabled=${lightbox.index === photos.length - 1}
                            onClick=${() => setLightbox((prev) => ({ ...prev, index: prev.index + 1 }))}
                        >›</button>
                    </div>
                    <div className="lightbox-name-row" onClick=${(e) => e.stopPropagation()}>
                        <span className="lightbox-name-label">📝 Nombre:</span>
                        <input
                            type="text"
                            className="lightbox-name-field"
                            value=${downloadName}
                            onInput=${(e) => setDownloadName(e.target.value)}
                            placeholder="JTC0000"
                        />
                    </div>
                    <a
                        href=${getPhotoProxyDownloadUrl(photos[lightbox.index], `${downloadName}.jpeg`)}
                        download
                        className="lightbox-download"
                        onClick=${(e) => e.stopPropagation()}
                    >⬇ Descargar esta foto</a>
                </div>
            </div>
        ` : null}
    `;
}
