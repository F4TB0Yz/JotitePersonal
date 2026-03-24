from datetime import datetime
from src.domain.interfaces.pdf_generator_provider import PdfGeneratorProvider
from src.domain.messenger import MessengerContact

# Importación condicional para evitar fallos si la librería no está instalada inmediatamente
try:
    from fpdf import FPDF
except ImportError:
    # Si fpdf no está, podemos lanzar una excepción al intentar usarlo o dejar que falle en ejecución
    class FPDF:
         def __init__(self): raise ImportError("La librería 'fpdf' o 'fpdf2' no está instalada.")

class PdfReportProviderImpl(PdfGeneratorProvider):
    """
    Implementación de PdfGeneratorProvider usando la librería FPDF.
    Usa un diseño limpio con título, fecha y tabla de datos.
    """

    def generate_pending_messengers_report(self, messengers: list[MessengerContact]) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        
        # Título
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 12, "Reporte de Mensajeros Pendientes", ln=True, align='C')
        
        # Fecha de generación
        pdf.set_font("Helvetica", '', 11)
        pdf.cell(0, 8, f"Fecha de Generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
        pdf.ln(10)

        # Header de la Tabla
        pdf.set_font("Helvetica", 'B', 12)
        # Ajuste de anchos para que sumen ~180-190 (A4 tiene ~190 útil)
        pdf.cell(95, 10, "Mensajero", border=1, align='C')
        pdf.cell(50, 10, "Teléfono", border=1, align='C')
        pdf.cell(40, 10, "Pendientes", border=1, ln=True, align='C')

        # Cuerpo de la Tabla
        pdf.set_font("Helvetica", '', 11)
        for m in messengers:
            # Si el mensajero tiene ciudad (fue seleccionado), añadirlo al nombre
            full_name = f"{m.name} - {m.city}" if m.city else str(m.name)
            # Recortar nombre si es muy largo para que quepa en la celda
            name_text = full_name[:45]
            phone_text = str(m.phone or "N/A")
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
