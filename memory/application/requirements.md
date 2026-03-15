# Application: Requirements & Use Cases

## Entidades Principales
- **Paquetes**: unidades físicas rastreadas.
- **Guías**: documentos de envío asociados a paquetes.
- **Mensajeros**: repartidores asignados a guías/rutas.

## Requisitos Funcionales
1. Generar informes que consoliden información de paquetes, guías y mensajeros.
2. Consumir la API interna de J&T usando cookies de sesión provistas por el usuario.
3. Visualizar el estado de los paquetes en una interfaz web moderna, ágil y reactiva.
4. Generar tarjetas de paquetes no entregados optimizadas para impresión en PDF directamente desde el navegador.
5. Exportar el consolidado a formato CSV.
6. **Sincronización de Estados**: El sistema debe ser capaz de traer aplicaciones de devolución y guardar una "fotografía" (snapshot) del estado en ese momento.

## Datos para Informes (Extraídos de API)
Para los informes de **paquetes, guías y mensajeros**, usaremos:
- **De la Guía**: `waybillNo`, `orderSourceName`, `senderName`, `receiverName`, `receiverCityName`, `packageChargeWeight`.
- **De los Mensajeros/Operadores**: `staffName`, `staffContact`, `scanByName` (del rastreo de POD).
- **De Excepciones**: `abnormalPieceName`, `remark`, `scanTime`.

## Casos de Uso
- [x] Cargar cookies/token de sesión.
- [x] Implementar cliente Python funcional para los 4 endpoints.
- [x] Diseñar lógica de consolidación de datos.
- [x] Extraer tiempos y ubicaciones detalladas (P6, firmas, dirección).
- [x] Procesar lista de guías a través de una página web.
- [x] Ver un panel visual con el listado de tarjetas y su estado.
- [x] Filtrar paquetes entregados y no entregados.
- [x] Exportar vistas filtradas a PDF utilizando las características de impresión del navegador.

## Notas de Implementación
- **2026-02-26**: La interfaz web ahora es un SPA en React 18 (ES Modules) que consume los endpoints existentes a través de servicios dedicados (`src/web_ui/static/js/services`).
- **2026-03-15**: Refactorización de servicios (`Returns`, `Novedades`, `KPIs`) para cumplimiento de **Clean Architecture** mediante la extracción de capas de repositorio (`*Repository`) e inyección de dependencias en constructores.
