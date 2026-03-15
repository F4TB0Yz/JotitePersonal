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

## Próximos Pasos
1. Validar rendimiento y visualización del Dark Mode PDF en los navegadores del usuario (Pendiente).
2. Monitorear estabilidad del sistema tras el desacoplamiento de persistencia.

