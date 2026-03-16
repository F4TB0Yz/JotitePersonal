# Context: Session & Current State

## Current Focus
- Refactorizando servicios para cumplir con el patrón Repository y desacoplar SQLAlchemy de la lógica de negocio.

## Recent Decisions
- **2026-02-24**: Estructura de memoria "Clean Architecture" aprobada e implementada en `/memory/`.
- **2026-02-24**: Objetivo del proyecto definidoPara los informes de **paquetes, guías y mensajeros**, usaremos:
- **De la Guía**: `waybillNo`, `orderSourceName`, `senderName`, `receiverName`, `receiverCityName`, `receiverDetailedAddress`, `packageChargeWeight`.
- **2026-02-24**: Decisión técnica clave — usar API interna de J&T con cookies (no automatizar login por CAPTCHA).
- **2026-02-24**: Registro de 4 endpoints clave y sus estructuras de datos.
- **2026-02-24**: Elección de Python como stack base con arquitectura desacoplada.
- **2026-02-24**: Prueba de API exitosa con `JTC000032130348`, confirmando que el `authToken` y los headers son correctos.
- **2026-02-24**: Implementación de lógica de entrega basada en el estado `Firmado`.
- **2026-02-24**: Refinamiento final del reporte CSV eliminando columnas innecesarias (incluyendo Arribo P6).
- **2026-02-24**: Agregada dirección detallada del destinatario (`receiverDetailedAddress`) al reporte.
- **2026-02-24**: El usuario aprueba el inicio de la Fase 2 (Interfaz web con FastAPI y Vanilla UI) para visualizar tarjetas de paquetes y generar PDFs.
- **2026-02-24**: Implementada la Fase 2 web. Se añadió procesamiento en tiempo real con WebSockets y soporte para exportar PDFs respetando el modo oscuro original.
- **2026-02-26**: Implementación de la capa de persistencia y refactorización de `ReturnsService` para incluir sincronización de snapshots.
- **2026-03-15**: Refactorización completa de los servicios `ReturnsService`, `NovedadesService` y `KPIService` aplicando el patrón **Repository** y desacoplando SQLAlchemy de la lógica de aplicación. Creación de `ReturnsRepository`, `NovedadesRepository` y `KPIRepository`, y estandarización de excepciones de dominio.
- **2026-03-15**: **Hotfix** en `main_web.py` para corregir el error en el loop de sincronización de devoluciones (`_run_returns_sync_cycle()`). Se añade el uso de `SessionLocal` para inyectar el parámetro `session` requerido por `_build_returns_service()`.
- **2026-03-15**: Refactorización de `ReportService` y `exporter.py`. Se habilitó el cruce de datos con repositorios locales (`ReturnsRepository`, `NovedadesRepository`) y se transformó la exportación CSV en un generador de streams de dominio puro (flujo de bytes), mitigando dependencias de infraestructura en útiles.
- **2026-03-15**: **UI**: Añadido el cactus como favicon (`/static/favicon.webp`) en plantillas de `index` y `login`, y ruta explícita `/favicon.ico` en el servidor.
- **2026-03-15**: **UI/Impresión**: Finalización del sistema de Tarjetas PDF/Impresión (RF4). Se implementó descarga CSV vía streams, Skeleton Loading para carga progresiva de guías, integración de Excepciones cruzadas en el cuerpo de la tarjeta, y refinamiento CSS Ink-Saver para impresión pura.
- **2026-03-15**: **Refactorización**: Unificación de lógica de estados y saneamiento de `waybills.py`. Moviendo búsqueda de firmas (`signer_name`) y prioridad de direcciones redundantes hacia `ReportService.py`, acortando y estabilizando el consumo de endpoints en el router.
- **2026-03-15**: **UI/Frontend**: Estabilización de reactividad y orden en el procesador de guías (`useWaybillProcessor.js`). Se introdujo placeholders precargados para conservar el orden visualizado, monitor pre-flight de estado de sesión (detección de 401), y lógica pura `parseInternalDate` para el filtrado seguro de tiempos.
- **2026-03-15**: **Configuración**: Cierre del ciclo de sincronización automática. Integración de `ConfigRepository.set_key` y `/api/config/token` para salvado inmediato del token de Tampermonkey, y refactorización de `JTClient._post` para inyección de token en cada petición.
- **2026-03-15**: **Configuración**: Reparación del backend para sincronización automática de sesión. Se habilitaron respuestas estables y logs sobre `/api/config/token` para alinearse con script de Tampermonkey con telemetría.
- **2026-03-16**: **Configuración**: Desacoplamiento de la identidad del nodo (Home Node Config). Se centralizó `home_network_id` ("1009") y `home_network_name` ("Cund-Punto6") en la base de datos de configuración y se pasó dinámicamente a `ReportService` y WebSocket metadata para uso reactivo.
- **2026-03-16**: **Filtrado**: Implementación de Jurisdicción Estricta por Paradero Actual. Se forzó `is_out_of_jurisdiction = True` en backend para cualquier escaneo fuera del Home Node (excepto si viene en ruta de arribo), y se retiró la excepción de devoluciones en el cliente.
- **2026-03-16**: **Filtrado**: Corrección de lógica de Fecha de Arribo por Nodo Local. Se ajustó `arrival_punto6` para leer estrictamente la última "Descarga/Llegada" dentro del `home_node_id` (1009), con fallback a eventos de recolección en el origen.
- **2026-03-16**: **Filtrado**: Optimización de detección de Arribo Local para historiales extensos. Se implementó filtrado de subsets `local_events` para hallar la primera presencia física absoluta del paquete en el Nodo.
- **2026-03-16**: **Filtrado**: Ampliación de ventana para paquetes rezagados. Se integró la pestaña "Rezagos (>15 días)" en la UI y se refinaron los logs de auditoría ante bloqueos del Filtro de Jurisdicción.

## Próximos Pasos
- **2026-03-16**: **Filtrado**: Corrección de falsos positivos en detección de firmas (Código 94 vs 100). Se excluyó estrictamente el id 94 de la función `_is_signed_event` y se añadió un flag de rollback si el último evento es una Excepción.
1. Validar rendimiento y visualización del Dark Mode PDF en los navegadores del usuario (Pendiente).
2. Monitorear estabilidad del sistema tras el desacoplamiento de persistencia.
