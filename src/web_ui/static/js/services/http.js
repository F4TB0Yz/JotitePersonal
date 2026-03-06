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
            detail = response.statusText || detail;
        }
        throw new Error(detail);
    }
    return response.json();
}

export function get(url) {
    return fetch(url, {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
    }).then(handleJson);
}

export function post(url, body) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin'
    }).then(handleJson);
}
