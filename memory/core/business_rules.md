# Core: Business Rules & Instructions

## Agent Instructions
- **Persistencia**: Cada decisión fundamental debe registrarse en los archivos de memoria correspondientes.
- **Pre-flight Check**: Leer todo el directorio `memory/` al inicio de cada sesión de trabajo.
- **Organización**: Seguir la estructura de Clean Architecture para la documentación.
- **Idioma**: El proyecto se comunica en español.

### Lineamientos UI (26-feb-2026)
- La nueva SPA React se organiza en capas: servicios HTTP (infraestructura), hooks/presenters (aplicación) y componentes (interfaz).
- Cada vista consume datos únicamente a través de los servicios compartidos para mantener independencia del backend.
- Las dependencias del frontend se distribuyen vía import map (React 18, ReactDOM y HTM) evitando toolchains adicionales.

## Objetivo del Proyecto
Optimizar el tiempo dedicado a la generación de **informes de paquetes, guías y mensajeros** para la operación de J&T Express, mediante automatización del proceso de recopilación de datos.

## Reglas de Negocio Inamovibles
1. **Autenticación via Cookies**: El login de J&T tiene CAPTCHA. La autenticación se gestiona manualmente por el usuario y se pasan las cookies directamente a la API interna. **Nunca** intentar automatizar el login.
2. **API Interna**: Se consume la API interna de J&T, no una API pública ni scraping del DOM.
3. **Informes**: Los informes deben cubrir: **paquetes**, **guías** y **mensajeros**.
4. **Persistencia Local**: Toda entidad crítica (como las Devoluciones/Snapshots) debe ser persistida localmente para permitir auditoría y trabajo offline.
5. **Gestión de Errores**: Es obligatorio el uso de las excepciones de dominio definidas en `src/domain/exceptions.py` (`DomainException`, `APIError`, etc.) en lugar de excepciones nativas genéricas.
