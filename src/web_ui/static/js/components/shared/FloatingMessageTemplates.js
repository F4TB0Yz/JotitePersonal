import { html, useState, useEffect, useRef } from '../../lib/ui.js';
import { post } from '../../services/http.js';

/* ─── Default templates: 3 categories × 2 tones ─── */
const DEFAULT_TEMPLATES = {
    verificacion_formal: `Estimado cliente: {destinatario}, nos comunicamos de J&T Express Colombia.

Le escribimos para realizar una verificación de su servicio {guia}. Debido a un reajuste en la logística entre ciudades, el sistema no muestra movimiento reciente; sin embargo, queremos confirmar si por alguna razón usted ya recibió su paquete.

¿Sería tan amable de confirmarnos el estado actual de su entrega? Esto nos permitirá normalizar la información en nuestro sistema o agilizar el proceso de búsqueda.

Quedamos atentos, ¡muchas gracias!`,

    verificacion_informal: `Hola, {destinatario} 👋

Te saludamos de J&T Express Colombia.

Te contactamos para verificar tu envío {guia}. Por un ajuste en la logística entre ciudades, el sistema no muestra movimiento reciente, pero queremos confirmar si ya recibiste tu paquete.

¿Podrías confirmarnos si ya lo tienes o si aún no te ha llegado? Esto nos ayuda a normalizar la info o agilizar la búsqueda.

¡Gracias! 🙏`,

    confirmacion_formal: `Estimado cliente: {destinatario}, le saludamos de J&T Express Colombia.

Le contactamos porque el paquete con guía {guia} figura en nuestro sistema como entregado el día {fecha_entrega}, recibido bajo el nombre de {destinatario}. Sin embargo, tenemos un reporte de novedad por falta de entrega.

¿Podría confirmarnos si ya tiene el paquete en sus manos o si desconoce la entrega? Esto nos ayuda a cerrar el caso o iniciar la investigación con el mensajero.

Quedamos atentos a su respuesta.`,

    confirmacion_informal: `Hola, {destinatario}

Te saludamos de J&T Express Colombia.

Te contactamos porque el paquete con guía {guia} figura en nuestro sistema como entregado el día {fecha_entrega}, recibido bajo el nombre de {destinatario}. Sin embargo, tenemos un reporte de novedad por falta de entrega.

Por favor, ¿podrías confirmarnos si ya tienes el paquete en tus manos o si desconoces la entrega? Esto nos ayuda a cerrar el caso o iniciar la investigación con el mensajero.`,

    programada_formal: `Estimado cliente: {destinatario}, nos comunicamos de J&T Express Colombia.

Le informamos que su paquete con guía {guia} se encuentra actualmente en proceso de distribución con destino a {ciudad}. Nuestro equipo de logística está trabajando para que la entrega se realice a la brevedad posible en la dirección {direccion}.

Si tiene alguna instrucción especial para la entrega o desea coordinar un horario, por favor háganoslo saber.

Quedamos atentos, ¡muchas gracias!`,

    programada_informal: `Hola, {destinatario} 👋

Te escribimos de J&T Express Colombia.

Tu paquete con guía {guia} ya está en camino hacia {ciudad}. Estamos trabajando para entregarlo lo antes posible en la dirección {direccion}.

Si necesitas darnos alguna indicación especial o coordinar la entrega, ¡avísanos!

¡Gracias! 🙏`
};

const CATEGORIES = [
    { id: 'verificacion', label: '🔍 Verificación', description: 'Entrega no reconocida / sin movimiento' },
    { id: 'confirmacion', label: '✅ Confirmación', description: 'Entregado pero reportado como no recibido' },
    { id: 'programada',   label: '📦 Entrega programada', description: 'Paquete en tránsito / próximo a entregar' }
];

const STORAGE_KEY = 'jt_message_templates';

function loadTemplates() {
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const parsed = JSON.parse(saved);
            return { ...DEFAULT_TEMPLATES, ...parsed };
        }
    } catch { /* ignore */ }
    return { ...DEFAULT_TEMPLATES };
}

function saveTemplates(templates) {
    try {
        const custom = {};
        for (const [key, val] of Object.entries(templates)) {
            if (val !== DEFAULT_TEMPLATES[key]) custom[key] = val;
        }
        if (Object.keys(custom).length > 0) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(custom));
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    } catch { /* ignore */ }
}

function interpolate(template, vars) {
    return template
        .replace(/\{destinatario\}/g, vars.destinatario || '___')
        .replace(/\{guia\}/g, vars.guia || '___')
        .replace(/\{ciudad\}/g, vars.ciudad || '___')
        .replace(/\{direccion\}/g, vars.direccion || '___')
        .replace(/\{fecha_entrega\}/g, vars.fecha_entrega || '___')
        .replace(/\{remitente\}/g, vars.remitente || '___');
}

export default function FloatingMessageTemplates() {
    const [isOpen, setIsOpen] = useState(false);
    const [category, setCategory] = useState('verificacion');
    const [tono, setTono] = useState('formal');
    const [templates, setTemplates] = useState(loadTemplates);
    const [editing, setEditing] = useState(false);
    const [editText, setEditText] = useState('');
    const [copied, setCopied] = useState(false);

    /* Waybill context (pre-filled from card or manual) */
    const [waybillInput, setWaybillInput] = useState('');
    const [waybillData, setWaybillData] = useState(null);
    const [loadingData, setLoadingData] = useState(false);
    const [dataError, setDataError] = useState('');

    const editRef = useRef(null);

    /* Listen for open-message-templates event from WaybillCard */
    useEffect(() => {
        const handler = (e) => {
            const d = e?.detail;
            if (!d) return;
            setWaybillData({
                destinatario: d.receiver || '',
                guia: d.waybill_no || '',
                ciudad: d.city || '',
                direccion: d.address || '',
                fecha_entrega: d.delivery_time || '',
                remitente: d.sender || ''
            });
            setWaybillInput(d.waybill_no || '');
            setDataError('');
            setEditing(false);
            setCopied(false);
            setIsOpen(true);
        };
        window.addEventListener('open-message-templates', handler);
        return () => window.removeEventListener('open-message-templates', handler);
    }, []);

    const templateKey = `${category}_${tono}`;
    const currentTemplate = templates[templateKey] || DEFAULT_TEMPLATES[templateKey] || '';
    const isCustom = templates[templateKey] !== DEFAULT_TEMPLATES[templateKey];

    const vars = waybillData || {
        destinatario: '', guia: '', ciudad: '', direccion: '', fecha_entrega: '', remitente: ''
    };
    const previewText = interpolate(currentTemplate, vars);

    const openPanel = () => {
        setCopied(false);
        setEditing(false);
        setIsOpen(true);
    };

    const closePanel = () => {
        setIsOpen(false);
        setEditing(false);
        setCopied(false);
    };

    const handleFetchData = async () => {
        const wb = String(waybillInput || '').trim().toUpperCase();
        if (!wb) { setDataError('Ingresa un número de guía.'); return; }
        setLoadingData(true);
        setDataError('');
        try {
            const resp = await post('/api/waybills/details', { waybills: [wb] });
            const detail = resp[wb];
            if (!detail) { setDataError('No se encontraron datos para esta guía.'); return; }
            setWaybillData({
                destinatario: detail.receiverName || '',
                guia: wb,
                ciudad: detail.receiverCity || '',
                direccion: detail.receiverAddress || '',
                fecha_entrega: detail.lastEventTime || '',
                remitente: ''
            });
        } catch (err) {
            setDataError(err.message || 'Error al consultar la guía.');
        } finally {
            setLoadingData(false);
        }
    };

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(previewText);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            /* fallback */
            const ta = document.createElement('textarea');
            ta.value = previewText;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const handleStartEdit = () => {
        setEditText(currentTemplate);
        setEditing(true);
        setCopied(false);
        requestAnimationFrame(() => editRef.current?.focus());
    };

    const handleSaveEdit = () => {
        const next = { ...templates, [templateKey]: editText };
        setTemplates(next);
        saveTemplates(next);
        setEditing(false);
    };

    const handleRestore = () => {
        const next = { ...templates, [templateKey]: DEFAULT_TEMPLATES[templateKey] };
        setTemplates(next);
        saveTemplates(next);
        setEditing(false);
    };

    const availableVars = [
        { tag: '{destinatario}', label: 'Destinatario' },
        { tag: '{guia}', label: 'Guía' },
        { tag: '{ciudad}', label: 'Ciudad' },
        { tag: '{direccion}', label: 'Dirección' },
        { tag: '{fecha_entrega}', label: 'Fecha entrega' },
        { tag: '{remitente}', label: 'Remitente' }
    ];

    const insertVar = (tag) => {
        if (!editRef.current) return;
        const ta = editRef.current;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const newText = editText.slice(0, start) + tag + editText.slice(end);
        setEditText(newText);
        requestAnimationFrame(() => {
            ta.selectionStart = ta.selectionEnd = start + tag.length;
            ta.focus();
        });
    };

    return html`
        <div className="floating-messages-wrapper no-print">
            <button
                type="button"
                className="floating-messages-btn"
                title="Plantillas de mensajes"
                onClick=${openPanel}
            >💬</button>

            ${isOpen ? html`
                <div className="barcode-overlay" onClick=${closePanel}>
                    <div className="barcode-window msg-tpl-window" onClick=${(e) => e.stopPropagation()}>
                        <header>
                            <div>
                                <p>Comunicación con clientes</p>
                                <h4>Plantillas de Mensajes</h4>
                            </div>
                            <button type="button" className="barcode-close" onClick=${closePanel}>Cerrar ✕</button>
                        </header>

                        <!-- Waybill data loader -->
                        <div className="msg-tpl-data-section">
                            <div className="msg-tpl-input-row">
                                <input
                                    type="text"
                                    className="form-input"
                                    placeholder="Número de guía…"
                                    value=${waybillInput}
                                    onChange=${(e) => setWaybillInput(e.target.value)}
                                    onKeyPress=${(e) => { if (e.key === 'Enter') handleFetchData(); }}
                                />
                                <button type="button" className="form-btn primary" onClick=${handleFetchData} disabled=${loadingData}>
                                    ${loadingData ? 'Cargando…' : 'Cargar datos'}
                                </button>
                            </div>
                            ${dataError ? html`<p className="barcode-error">${dataError}</p>` : null}
                            ${waybillData ? html`
                                <div className="msg-tpl-data-pills">
                                    ${waybillData.destinatario ? html`<span className="msg-pill">👤 ${waybillData.destinatario}</span>` : null}
                                    ${waybillData.ciudad ? html`<span className="msg-pill">📍 ${waybillData.ciudad}</span>` : null}
                                    ${waybillData.fecha_entrega ? html`<span className="msg-pill">📅 ${waybillData.fecha_entrega}</span>` : null}
                                </div>
                            ` : null}
                        </div>

                        <!-- Tone toggle -->
                        <div className="msg-tpl-toggle-row">
                            <button
                                type="button"
                                className=${`msg-tpl-toggle-btn ${tono === 'formal' ? 'active' : ''}`}
                                onClick=${() => { setTono('formal'); setEditing(false); setCopied(false); }}
                            >Formal (usted)</button>
                            <button
                                type="button"
                                className=${`msg-tpl-toggle-btn ${tono === 'informal' ? 'active' : ''}`}
                                onClick=${() => { setTono('informal'); setEditing(false); setCopied(false); }}
                            >Informal (tú)</button>
                        </div>

                        <!-- Category tabs -->
                        <div className="msg-tpl-categories">
                            ${CATEGORIES.map((cat) => html`
                                <button
                                    key=${cat.id}
                                    type="button"
                                    className=${`msg-tpl-cat-btn ${category === cat.id ? 'active' : ''}`}
                                    title=${cat.description}
                                    onClick=${() => { setCategory(cat.id); setEditing(false); setCopied(false); }}
                                >${cat.label}</button>
                            `)}
                        </div>

                        <!-- Preview / Edit -->
                        ${editing ? html`
                            <div className="msg-tpl-edit-section">
                                <div className="msg-tpl-var-chips">
                                    ${availableVars.map((v) => html`
                                        <button key=${v.tag} type="button" className="msg-var-chip"
                                            onClick=${() => insertVar(v.tag)}
                                            title=${'Insertar ' + v.label}
                                        >${v.tag}</button>
                                    `)}
                                </div>
                                <textarea
                                    ref=${editRef}
                                    className="msg-tpl-textarea"
                                    value=${editText}
                                    onInput=${(e) => setEditText(e.target.value)}
                                    rows="10"
                                ></textarea>
                                <div className="msg-tpl-edit-actions">
                                    <button type="button" className="form-btn primary" onClick=${handleSaveEdit}>💾 Guardar</button>
                                    <button type="button" className="form-btn" onClick=${() => setEditing(false)}>Cancelar</button>
                                </div>
                            </div>
                        ` : html`
                            <div className="msg-tpl-preview">${previewText}</div>
                        `}

                        <!-- Actions -->
                        ${!editing ? html`
                            <div className="msg-tpl-actions">
                                <button type="button" className="form-btn primary msg-copy-btn" onClick=${handleCopy}>
                                    ${copied ? '✅ ¡Copiado!' : '📋 Copiar mensaje'}
                                </button>
                                <button type="button" className="form-btn" onClick=${handleStartEdit}>✏️ Editar</button>
                                ${isCustom ? html`
                                    <button type="button" className="form-btn msg-restore-btn" onClick=${handleRestore}>🔄 Restaurar</button>
                                ` : null}
                            </div>
                        ` : null}
                    </div>
                </div>
            ` : null}
        </div>
    `;
}
