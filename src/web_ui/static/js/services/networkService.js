import { get, post } from './http.js';

export async function fetchPendingWaybills(networkCode, start, end) {
    const response = await post('/api/network/waybills', {
        networkCode,
        startTime: start,
        endTime: end,
        signType: 0
    });

    if (!response.job_id) {
        return response;
    }

    const taskId = response.job_id;
    return new Promise((resolve, reject) => {
        const interval = setInterval(async () => {
            try {
                const statusRes = await get(`/api/network/waybills/task/${taskId}`);
                if (statusRes.status === 'completed') {
                    clearInterval(interval);
                    resolve(statusRes.data);
                } else if (statusRes.status === 'error') {
                    clearInterval(interval);
                    reject(new Error(statusRes.error || 'Error en la petición de red (Background)'));
                }
            } catch (err) {
                clearInterval(interval);
                reject(err);
            }
        }, 3000);
    });
}
