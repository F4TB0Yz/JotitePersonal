import { createRoot } from 'react-dom/client';
import { React } from './lib/ui.js';
import App from './App.js';

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('root');
    if (!container) return;
    const root = createRoot(container);
    root.render(React.createElement(App));
});
