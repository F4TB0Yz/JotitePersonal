import unicodedata
from datetime import datetime
from src.domain.interfaces.pdf_generator_provider import PdfGeneratorProvider
from src.domain.messenger import MessengerContact

# Importación condicional para evitar fallos si la librería no está instalada inmediatamente
try:
    from fpdf import FPDF
except ImportError:
    # Si fpdf no está, podemos lanzar una excepción al intentar usarlo o dejar que falle en ejecución
    class FPDF:
         def __init__(self): raise ImportError("La librería 'fpdf' no está instalada.")

def _sanitize_latin1(text: str) -> str:
    """Elimina o reemplaza caracteres que hacen colapsar a FPDF (solo soporta latin-1)."""
    if not text:
        return ""
    # Normaliza a NFKD (separa caracteres de sus diacríticos)
    normalized = unicodedata.normalize('NFKD', str(text))
    # Codifica a latin-1 reemplazando lo incompatible con '?' y decodifica de vuelta
    return normalized.encode('latin-1', 'replace').decode('latin-1')

class PdfReportProviderImpl(PdfGeneratorProvider):
    """
    Implementación de PdfGeneratorProvider usando la librería FPDF.
    Usa un diseño limpio con título, fecha y tabla de datos.
    Soporta sanitización de caracteres Unicode para evitar UnicodeEncodeError.
    """

    def generate_pending_messengers_report(self, messengers: list[MessengerContact]) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        
        # Título
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 12, _sanitize_latin1("Reporte de Mensajeros Pendientes"), ln=True, align='C')
        
        # Fecha de generación
        pdf.set_font("Helvetica", '', 11)
        pdf.cell(0, 8, _sanitize_latin1(f"Fecha de Generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), ln=True, align='C')
        pdf.ln(10)

        # Header de la Tabla
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(95, 10, _sanitize_latin1("Mensajero"), border=1, align='C')
        pdf.cell(50, 10, _sanitize_latin1("Teléfono"), border=1, align='C')
        pdf.cell(40, 10, _sanitize_latin1("Pendientes"), border=1, ln=True, align='C')

        # Cuerpo de la Tabla
        pdf.set_font("Helvetica", '', 11)
        for m in messengers:
            full_name = f"{m.name} - {m.city}" if m.city else str(m.name)
            
            # SANITIZACIÓN CRÍTICA ANTES DE DIBUJAR EN EL PDF
            name_text = _sanitize_latin1(full_name[:45])
            phone_text = _sanitize_latin1(str(m.phone or "N/A"))
            count_text = str(m.pending_count or 0)

            pdf.cell(95, 10, name_text, border=1)
            pdf.cell(50, 10, phone_text, border=1, align='C')
            pdf.cell(40, 10, count_text, border=1, ln=True, align='C')

        # Soporte para fpdf2 (retorna bytes) y fpdf antigua (retorna str con dest='S')
        try:
            out = pdf.output()
            if isinstance(out, bytes):
                return out
            return str(out).encode('latin1')
        except TypeError:
            # Fallback para fpdf antigua si el anterior fallara
            return pdf.output(dest='S').encode('latin1')
