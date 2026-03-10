const _RETRY_STATUSES = new Set([502, 503, 504]);
const _RETRY_DELAYS = [1000, 3000]; // ms

async function _fetchWithRetry(url, options) {
    let lastResponse;
    for (let attempt = 0; attempt <= _RETRY_DELAYS.length; attempt++) {
        lastResponse = await fetch(url, options);
        if (!_RETRY_STATUSES.has(lastResponse.status) || attempt === _RETRY_DELAYS.length) {
            return lastResponse;
        }
        await new Promise(r => setTimeout(r, _RETRY_DELAYS[attempt]));
    }
    return lastResponse;
}

async function handleJson(response) {
    if (!response.ok) {
        if (response.status === 401) {
            if (window.location.pathname !== '/login') {
                window.location.assign('/login');
            }
            throw new Error('No autenticado');
        }

        let detail = 'Error desconocido';
        try {
            const data = await response.json();
            detail = data.detail || data.error || JSON.stringify(data);
        } catch (err) {
            detail = _RETRY_STATUSES.has(response.status)
                ? 'Servidor temporalmente no disponible'
                : (response.statusText || detail);
        }
        throw new Error(detail);
    }
    return response.json();
}

export function get(url) {
    return _fetchWithRetry(url, {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
    }).then(handleJson);
}

export function post(url, body) {
    return _fetchWithRetry(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin'
    }).then(handleJson);
}
