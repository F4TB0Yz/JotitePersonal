import { html, Fragment } from '../../lib/ui.js';
import NovedadesModal from '../shared/NovedadesModal.js';
import WaybillQueryModal from '../shared/WaybillQueryModal.js';
import FloatingBarcodeScanner from '../shared/FloatingBarcodeScanner.js';
import FloatingReprintButton from '../shared/FloatingReprintButton.js';
import FloatingPhoneLookup from '../shared/FloatingPhoneLookup.js';
import FloatingMessengerPhone from '../shared/FloatingMessengerPhone.js';
import FloatingMessageTemplates from '../shared/FloatingMessageTemplates.js';
import FloatingDailyReport from '../shared/FloatingDailyReport.js';
import CommandPalette from '../shared/CommandPalette.js';

export default function GlobalOverlays() {
    return html`
        <${Fragment}>
            <${NovedadesModal} />
            <${WaybillQueryModal} />
            <${FloatingMessageTemplates} />
            <${FloatingPhoneLookup} />
            <${FloatingReprintButton} />
            <${FloatingBarcodeScanner} />
            <${FloatingMessengerPhone} />
            <${FloatingDailyReport} />
            <${CommandPalette} />
        </${Fragment}>
    `;
}
