let socket = null;
let reconnectTimer = null;
let initialized = false;

function dispatchTemuNotification(payload) {
    window.dispatchEvent(new CustomEvent('temu-breach-predicted', { detail: payload }));
}

function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/notifications`;

    socket = new WebSocket(url);

    socket.onopen = () => {
        try {
            socket.send('subscribe');
        } catch (err) {
            console.error('No se pudo enviar handshake de notificaciones', err);
        }
    };

    socket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data || '{}');
            if (message.type === 'temu_breach_predicted' && message.payload) {
                dispatchTemuNotification(message.payload);
            }
        } catch (err) {
            console.error('Error parseando notificación WS', err);
        }
    };

    socket.onclose = () => {
        socket = null;
        if (!initialized) return;
        reconnectTimer = window.setTimeout(() => connect(), 5000);
    };

    socket.onerror = () => {
        try {
            socket?.close();
        } catch (_err) {
            // ignore
        }
    };
}

export function initNotificationSocket() {
    if (typeof window === 'undefined') return;
    if (initialized) return;
    initialized = true;
    connect();
}

export function stopNotificationSocket() {
    initialized = false;
    if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    if (socket) {
        try {
            socket.close();
        } catch (_err) {
            // ignore
        }
        socket = null;
    }
}
