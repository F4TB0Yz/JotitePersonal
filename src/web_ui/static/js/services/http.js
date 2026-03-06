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
    return fetch(url, { headers: { 'Accept': 'application/json' } }).then(handleJson);
}

export function post(url, body) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body)
    }).then(handleJson);
}
