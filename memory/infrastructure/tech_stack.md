# Infrastructure: Tech Stack & Tools

## Autenticación
- **Método**: Cookies de sesión (manual). El usuario hace login en el navegador y extrae las cookies.
- **Razón**: El login de J&T usa CAPTCHA, por lo que no se puede automatizar.

## API: Endpoints Identificados
Todos los endpoints son `POST` a `https://gw.jtexpress.co/operatingplatform/`.

### Headers Comunes
- `authToken`: Token dinámico (necesario extraer del navegador).
- `Content-Type`: `application/json;charset=UTF-8`
- `lang/langType`: `ES`
- `routeName`: `trackingExpress`
- `timezone`: `GMT-0500`

### Endpoints
1.  **Detalle de Orden**: `/order/getOrderDetail`
    - **Payload**: `{"waybillNo": "GUID", "countryId": "1"}`
    - **Datos clave**: Info de remitente, destinatario, peso, red de origen/destino.
2.  **Escaneo de Excepciones**: `/abnormalPieceScanList/pageList`
    - **Payload**: `{"current": 1, "size": 100, "waybillId": "GUID", "countryId": "1"}`
    - **Datos clave**: Historial de problemas (trafico, etc), operador que escaneó.
3.  **Muro de Mensajes**: `/messageBoard/list`
    - **Payload**: `{"current": 1, "size": 1000, "waybillNo": "GUID", "countryId": "1"}`
4.  **Rastreo Completo (Tracking)**: `/podTracking/inner/query/keywordList`
    - **Payload**: `{"keywordList": ["GUID"], "trackingTypeEnum": "WAYBILL", "countryId": "1"}`
    - **Datos clave**: Línea de tiempo completa, firmas, nombres de mensajeros y transportadores.

## Stack Técnico
- **Backend**: Python (FastAPI)
- **Persistencia**: SQLAlchemy (1.4+/2.0) con soporte para SQLite como base de datos local.
- **Migraciones**: Sistema de inicialización automática y migraciones en `src/infrastructure/database/migrations.py`.
- **Frontend**: React 18 vía ESM/Import Maps sin build step. Los componentes viven en `src/web_ui/static/js`, con `main.js` montando la SPA sobre `#root` definido en la plantilla.
- **Estilos**: CSS sin preprocesador, manteniendo el diseño glassmorphism y reglas de impresión existentes.
- **Fase Actual**: Fase 2 (Interfaz Web).
- **Formato de Salida**: 
  - Visual en navegador (Tarjetas dinámicas).
  - Exportación nativa a PDF (Impresión configurada por CSS).
  - Descarga de CSV (Reutilizando la lógica existente).

## Principio de Arquitectura (Clean Architecture)
El código sigue fuertemente desacoplado:
- `api/` → Cliente HTTP hacia J&T.
- `services/` → Lógica de negocio (ReportService).
- `models/` → Estructuras de datos puras.
- `web_ui/` **[NUEVA CAPA]** → Servidor FastAPI, endpoints de la UI (`main_web.py`), plantillas HTML y recursos estáticos. Es totalmente independiente de cómo se obtienen los datos.

## Pendientes de Infraestructura
- [x] Decidir stack tecnológico del proyecto (Python).
- [ ] Recibir y documentar los endpoints identificados por el usuario.
- [ ] Definir cómo el usuario proveerá las cookies al sistema.
