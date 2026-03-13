const _RETRY_STATUSES = new Set([502, 503, 504]);
const _RETRY_DELAYS = [1000, 3000]; // ms

async function _fetchWithRetry(url, options) {
    try {
        let response;
        for (let attempt = 0; attempt <= _RETRY_DELAYS.length; attempt++) {
            response = await fetch(url, options);

            // Validación inmediata de estado antes de cualquier procesamiento
            if (response.status === 401 || response.status === 403) {
                window.location.href = '/login';
                throw new Error('Sesión expirada o acceso denegado');
            }

            if (response.status >= 500) {
                if (_RETRY_STATUSES.has(response.status) && attempt < _RETRY_DELAYS.length) {
                    await new Promise(r => setTimeout(r, _RETRY_DELAYS[attempt]));
                    continue;
                }
                throw new Error('Error interno del servidor. Intente nuevamente.');
            }

            return response;
        }
        return response;
    } catch (err) {
        if (err.name === 'TypeError' || err.message.toLowerCase().includes('fetch')) {
            throw new Error('Error de conexión con el servidor');
        }
        throw err;
    }
}

async function handleJson(response) {
    if (!response.ok) {
        let detail = 'Error desconocido';
        try {
            const data = await response.json();
            detail = data.detail || data.error || JSON.stringify(data);
        } catch (err) {
            detail = response.statusText || detail;
        }
        throw new Error(detail);
    }
    return response.json();
}

export function get(url) {
    return _fetchWithRetry(url, {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
    }).then(r => r && handleJson(r));
}

export function post(url, body) {
    return _fetchWithRetry(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin'
    }).then(r => r && handleJson(r));
}

export function httpDelete(url) {
    return _fetchWithRetry(url, {
        method: 'DELETE',
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
    }).then(r => r && handleJson(r));
}

export function patch(url, body) {
    return _fetchWithRetry(url, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin'
    }).then(r => r && handleJson(r));
}
