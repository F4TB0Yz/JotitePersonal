import { html, useState, useEffect, useRef } from '../../lib/ui.js';

export default function NovedadesModal() {
    const [isOpen, setIsOpen] = useState(false);
    const [activeTab, setActiveTab] = useState('lista'); // 'lista' o 'nueva'
    
    // Lista state
    const [novedades, setNovedades] = useState([]);
    const [isLoadingList, setIsLoadingList] = useState(false);
    const [filterWaybill, setFilterWaybill] = useState('');
    
    // Form state
    const [formData, setFormData] = useState({
        waybill: '',
        description: '',
        status: 'Pendiente',
        type_cat: 'Mensajero'
    });
    const [files, setFiles] = useState([]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    
    const fileInputRef = useRef(null);

    // Escuchar eventos globales para abrir modal
    useEffect(() => {
        const handleOpen = (e) => {
            setIsOpen(true);
            const data = e.detail;
            
            if (data && data.waybill) {
                // Pre-llenar y pasar a tab "nueva" si viene de WaybillCard
                setFormData(prev => ({ ...prev, waybill: data.waybill }));
                setActiveTab('nueva');
                setFilterWaybill(data.waybill);
            } else {
                // Abrir en lista por defecto
                setActiveTab('lista');
                setFilterWaybill('');
                fetchNovedades();
            }
        };

        window.addEventListener('open-novedades-modal', handleOpen);
        return () => window.removeEventListener('open-novedades-modal', handleOpen);
    }, []);

    // Cargar novedades cuando se abre lista
    useEffect(() => {
        if (isOpen && activeTab === 'lista') {
            fetchNovedades(filterWaybill);
        }
    }, [isOpen, activeTab]);

    const fetchNovedades = async (waybill = '') => {
        setIsLoadingList(true);
        try {
            const url = waybill ? `/api/novedades?waybill=${encodeURIComponent(waybill)}` : '/api/novedades';
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setNovedades(data);
            }
        } catch (error) {
            console.error("Error al cargar novedades:", error);
        } finally {
            setIsLoadingList(false);
        }
    };

    const handleClose = () => {
        setIsOpen(false);
        setTimeout(() => setFiles([]), 300); // Limpiar después de animación
    };

    const handleTabChange = (tab) => {
        setActiveTab(tab);
        if (tab === 'lista') fetchNovedades(filterWaybill);
    };

    const handleFormChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleFileChange = (e) => {
        setFiles(Array.from(e.target.files));
    };

    const handleFormSubmit = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);

        const apiFormData = new FormData();
        apiFormData.append('waybill', formData.waybill);
        apiFormData.append('description', formData.description);
        apiFormData.append('status', formData.status);
        apiFormData.append('type_cat', formData.type_cat);
        
        files.forEach(file => {
            apiFormData.append('files', file);
        });

        try {
            const res = await fetch('/api/novedades', {
                method: 'POST',
                body: apiFormData // No se envía Content-Type explícitamente cuando es FormData
            });
            
            if (res.ok) {
                // Reset form
                setFormData(prev => ({ ...prev, description: '' })); // Dejamos el waybill por si acaso
                setFiles([]);
                if (fileInputRef.current) fileInputRef.current.value = '';
                
                // Mostrar alerta / notificación
                setActiveTab('lista'); // Volver a la lista
            } else {
                alert('No se pudo guardar la novedad');
            }
        } catch (err) {
            console.error('Error al enviar novedad:', err);
            alert('Error de conexión');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleStatusChange = async (id, newStatus) => {
        try {
            const res = await fetch(`/api/novedades/${id}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });
            if (res.ok) {
                // Update local list
                setNovedades(prev => prev.map(nov => 
                    nov.id === id ? { ...nov, status: newStatus } : nov
                ));
            }
        } catch (err) {
            console.error("No se pudo actualizar estado", err);
        }
    };

    if (!isOpen) return null;

    // Helper functions for UI
    const getStatusColor = (status) => {
        switch(status) {
            case 'Resuelto': return 'var(--success-color, #2ea043)';
            case 'En Proceso': return 'var(--warning-color, #d29922)';
            default: return 'var(--accent-color)';
        }
    };

    return html`
        <div className="novedades-modal-overlay ${isOpen ? 'active' : ''}" onClick=${(e) => e.target.classList.contains('novedades-modal-overlay') && handleClose()}>
            <div className="novedades-modal-content">
                
                <!-- HEADER -->
                <div className="novedades-modal-header">
                    <h2>Centro de Novedades</h2>
                    <button className="close-btn" onClick=${handleClose}>×</button>
                </div>

                <!-- TABS -->
                <div className="novedades-tabs">
                    <button 
                        className="tab-btn ${activeTab === 'lista' ? 'active' : ''}" 
                        onClick=${() => handleTabChange('lista')}>
                        🗂️ Historial
                    </button>
                    <button 
                        className="tab-btn ${activeTab === 'nueva' ? 'active' : ''}" 
                        onClick=${() => handleTabChange('nueva')}>
                        ➕ Nueva Novedad
                    </button>
                </div>

                <!-- BODY -->
                <div className="novedades-modal-body">
                    
                    ${activeTab === 'lista' ? html`
                        <div className="novedades-list-container">
                            <div className="novedades-filters">
                                <input 
                                    type="text" 
                                    value=${filterWaybill}
                                    onChange=${(e) => setFilterWaybill(e.target.value)}
                                    placeholder="🔍 Filtrar por Waybill..." 
                                    className="form-input"
                                />
                                <button className="form-btn" onClick=${() => fetchNovedades(filterWaybill)}>Buscar</button>
                                ${filterWaybill && html`
                                    <button className="form-btn outline" onClick=${() => { setFilterWaybill(''); fetchNovedades(''); }}>Limpiar</button>
                                `}
                            </div>
                            
                            ${isLoadingList ? html`<p className="loading-msg">Cargando...</p>` : ''}
                            
                            ${!isLoadingList && novedades.length === 0 ? html`
                                <div className="empty-state">No hay novedades registradas.</div>
                            ` : ''}

                            <div className="novedades-cards">
                                ${novedades.map(nov => html`
                                    <div className="novedad-card" key=${nov.id}>
                                        <div className="nav-card-header">
                                            <strong>#${nov.waybill}</strong>
                                            <span 
                                                className="status-badge" 
                                                style=${{ background: getStatusColor(nov.status) }}
                                                onClick=${() => {
                                                    const nextStatus = nov.status === 'Pendiente' ? 'En Proceso' : (nov.status === 'En Proceso' ? 'Resuelto' : 'Pendiente');
                                                    handleStatusChange(nov.id, nextStatus);
                                                }}
                                                title="Click para cambiar estado"
                                            >
                                                ${nov.status}
                                            </span>
                                        </div>
                                        <div className="nav-card-meta">
                                            <span className="type-badge">${nov.type}</span>
                                            <span className="date-badge">${new Date(nov.created_at).toLocaleString()}</span>
                                        </div>
                                        <p className="nav-card-desc">${nov.description}</p>
                                        
                                        ${nov.images && nov.images.length > 0 ? html`
                                            <div className="nav-card-images">
                                                ${nov.images.map((img, i) => html`
                                                    <a href=${img} target="_blank" rel="noopener noreferrer" key=${i}>
                                                        <img src=${img} alt="Evidencia" className="nav-thumbnail" loading="lazy"/>
                                                    </a>
                                                `)}
                                            </div>
                                        ` : ''}
                                    </div>
                                `)}
                            </div>
                        </div>
                    ` : ''}

                    ${activeTab === 'nueva' ? html`
                        <form className="novedad-form" onSubmit=${handleFormSubmit}>
                            <div className="form-group row">
                                <div className="input-group">
                                    <label>Waybill</label>
                                    <input 
                                        type="text" 
                                        className="form-input" 
                                        name="waybill"
                                        value=${formData.waybill}
                                        onChange=${handleFormChange}
                                        required 
                                        placeholder="Ingrese el local num..."
                                    />
                                </div>
                                <div className="input-group">
                                    <label>Estado</label>
                                    <select className="form-input" name="status" value=${formData.status} onChange=${handleFormChange}>
                                        <option value="Pendiente">Pendiente</option>
                                        <option value="En Proceso">En Proceso</option>
                                        <option value="Resuelto">Resuelto</option>
                                    </select>
                                </div>
                            </div>
                            
                            <div className="form-group">
                                <label>Categoría / Tipo</label>
                                <select className="form-input" name="type_cat" value=${formData.type_cat} onChange=${handleFormChange}>
                                    <option value="Mensajero">Problema con Mensajero</option>
                                    <option value="Cliente">Solicitud de Cliente</option>
                                    <option value="Dirección">Dirección Incorrecta / Incompleta</option>
                                    <option value="Siniestro">Siniestro / Daño</option>
                                    <option value="Operativo">Retraso Operativo / Bodega</option>
                                    <option value="Otro">Otro</option>
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Descripción de la Novedad</label>
                                <textarea 
                                    className="form-input textarea" 
                                    name="description"
                                    value=${formData.description}
                                    onChange=${handleFormChange}
                                    required
                                    rows="4" 
                                    placeholder="Describe qué sucedió o qué acción se tomó..."
                                ></textarea>
                            </div>

                            <div className="form-group">
                                <label>Imágenes de Prueba (Opcional)</label>
                                <input 
                                    type="file" 
                                    accept="image/*" 
                                    multiple 
                                    onChange=${handleFileChange}
                                    ref=${fileInputRef}
                                    className="file-input"
                                />
                                ${files.length > 0 ? html`
                                    <div className="file-preview-list">
                                        ${files.map(f => html`<span className="file-badge">📎 ${f.name}</span>`)}
                                    </div>
                                ` : ''}
                            </div>

                            <div className="form-actions">
                                <button type="button" className="form-btn outline" onClick=${handleClose}>Cancelar</button>
                                <button type="submit" className="form-btn primary" disabled=${isSubmitting}>
                                    ${isSubmitting ? 'Guardando...' : '💾 Guardar Novedad'}
                                </button>
                            </div>
                        </form>
                    ` : ''}

                </div>
            </div>
        </div>
    `;
}
