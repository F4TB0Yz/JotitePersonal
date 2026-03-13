import { useState, useEffect, useCallback } from '../lib/ui.js';

export default function useBarcodeCarousel(barcodeItems) {
    const [barcodeModal, setBarcodeModal] = useState({ open: false, items: [], index: 0 });

    const openBarcodeViewer = useCallback((startIndex = 0) => {
        if (!barcodeItems.length) return;
        const safeIndex = Math.min(Math.max(startIndex, 0), barcodeItems.length - 1);
        setBarcodeModal({ open: true, items: barcodeItems, index: safeIndex });
    }, [barcodeItems]);

    const closeBarcodeViewer = useCallback(() => {
        setBarcodeModal((prev) => ({ ...prev, open: false }));
    }, []);

    const shiftBarcode = useCallback((delta) => {
        setBarcodeModal((prev) => {
            if (!prev.items.length) return prev;
            const nextIndex = (prev.index + delta + prev.items.length) % prev.items.length;
            return { ...prev, index: nextIndex };
        });
    }, []);

    useEffect(() => {
        if (!barcodeModal.open) return undefined;
        const handleKey = (event) => {
            if (event.key === 'Escape') {
                event.preventDefault();
                closeBarcodeViewer();
            } else if (event.key === 'ArrowRight') {
                shiftBarcode(1);
            } else if (event.key === 'ArrowLeft') {
                shiftBarcode(-1);
            }
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [barcodeModal.open, closeBarcodeViewer, shiftBarcode]);

    useEffect(() => {
        if (!barcodeModal.open) return;
        setBarcodeModal((prev) => {
            if (!barcodeItems.length) {
                return { open: false, items: [], index: 0 };
            }
            const safeIndex = Math.min(prev.index, barcodeItems.length - 1);
            return { ...prev, items: barcodeItems, index: safeIndex };
        });
    }, [barcodeItems, barcodeModal.open]);

    return { barcodeModal, openBarcodeViewer, closeBarcodeViewer, shiftBarcode };
}
