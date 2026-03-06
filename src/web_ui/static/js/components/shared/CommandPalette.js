import { html, useEffect, useMemo, useRef, useState } from '../../lib/ui.js';
import { globalSearch } from '../../services/searchService.js';

function flattenResults(data) {
    const rows = [];

    (data.waybills || []).forEach((item) => {
        rows.push({
            key: `wb-${item.waybill_no}`,
            type: 'waybill',
            title: item.waybill_no,
            subtitle: `${item.receiver || 'N/A'} · ${item.city || 'N/A'}`,
            payload: item
        });
    });

    (data.messengers || []).forEach((item) => {
        const name = item.accountName || 'Mensajero';
        const code = item.accountCode || 'Sin código';
        rows.push({
            key: `ms-${code}-${name}`,
            type: 'messenger',
            title: name,
            subtitle: `${code} · ${item.customerNetworkName || 'Sin red'}`,
            payload: item
        });
    });

    (data.novedades || []).forEach((item) => {
        rows.push({
            key: `nv-${item.id}`,
            type: 'novedad',
            title: `${item.waybill} · ${item.type}`,
            subtitle: item.description,
            payload: item
        });
    });

    return rows;
}

export default function CommandPalette() {
    const [isOpen, setIsOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState({ waybills: [], messengers: [], novedades: [] });
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef(null);

    useEffect(() => {
        const onKeyDown = (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setIsOpen(true);
            }
            if (e.key === 'Escape') {
                setIsOpen(false);
            }
        };

        const onOpen = () => setIsOpen(true);

        window.addEventListener('keydown', onKeyDown);
        window.addEventListener('open-command-palette', onOpen);
        return () => {
            window.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('open-command-palette', onOpen);
        };
    }, []);

    useEffect(() => {
        if (!isOpen) return;
        const id = setTimeout(() => inputRef.current?.focus(), 0);
        return () => clearTimeout(id);
    }, [isOpen]);

    useEffect(() => {
        if (!isOpen) return;
        if ((query || '').trim().length < 2) {
            setResults({ waybills: [], messengers: [], novedades: [] });
            setSelectedIndex(0);
            return;
        }

        const id = setTimeout(() => {
            setLoading(true);
            globalSearch(query)
                .then((data) => {
                    setResults(data || { waybills: [], messengers: [], novedades: [] });
                    setSelectedIndex(0);
                })
                .catch(() => setResults({ waybills: [], messengers: [], novedades: [] }))
                .finally(() => setLoading(false));
        }, 220);

        return () => clearTimeout(id);
    }, [query, isOpen]);

    const rows = useMemo(() => flattenResults(results), [results]);

    const close = () => {
        setIsOpen(false);
        setQuery('');
        setResults({ waybills: [], messengers: [], novedades: [] });
        setSelectedIndex(0);
    };

    const executeAction = (row) => {
        if (!row) return;

        if (row.type === 'waybill') {
            window.dispatchEvent(new CustomEvent('open-query-modal', { detail: { waybill: row.payload.waybill_no } }));
            close();
            return;
        }

        if (row.type === 'messenger') {
            window.dispatchEvent(new CustomEvent('navigate-view', { detail: { view: 'mensajeros' } }));
            window.dispatchEvent(new CustomEvent('open-messenger-from-search', { detail: { messenger: row.payload } }));
            close();
            return;
        }

        if (row.type === 'novedad') {
            window.dispatchEvent(new CustomEvent('open-novedades-modal', { detail: { waybill: row.payload.waybill } }));
            close();
        }
    };

    const onOverlayKeyDown = (e) => {
        if (!rows.length) return;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIndex((prev) => (prev + 1) % rows.length);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIndex((prev) => (prev - 1 + rows.length) % rows.length);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            executeAction(rows[selectedIndex]);
        }
    };

    if (!isOpen) return null;

    return html`
        <div className="command-palette-overlay" onClick=${(e) => e.target === e.currentTarget && close()} onKeyDown=${onOverlayKeyDown}>
            <div className="command-palette-panel">
                <div className="command-palette-input-wrap">
                    <span className="command-palette-icon">⌘</span>
                    <input
                        ref=${inputRef}
                        className="command-palette-input"
                        type="text"
                        value=${query}
                        onChange=${(e) => setQuery(e.target.value)}
                        placeholder="Buscar guías, mensajeros o novedades..."
                    />
                    <span className="command-palette-hint">Ctrl+K</span>
                </div>

                <div className="command-palette-results">
                    ${loading ? html`<div className="command-palette-empty">Buscando...</div>` : null}
                    ${!loading && rows.length === 0
                        ? html`<div className="command-palette-empty">Escribe al menos 2 caracteres</div>`
                        : null}
                    ${rows.map((row, index) => html`
                        <button
                            type="button"
                            key=${row.key}
                            className=${`command-palette-item ${index === selectedIndex ? 'active' : ''}`}
                            onMouseEnter=${() => setSelectedIndex(index)}
                            onClick=${() => executeAction(row)}
                        >
                            <span className=${`command-palette-tag ${row.type}`}>${row.type}</span>
                            <span className="command-palette-main">
                                <strong>${row.title}</strong>
                                <small>${row.subtitle}</small>
                            </span>
                        </button>
                    `)}
                </div>
            </div>
        </div>
    `;
}
