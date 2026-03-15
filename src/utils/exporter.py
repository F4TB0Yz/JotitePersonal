import csv
import io
from typing import List, Dict, Any, Union
from src.models.waybill import ConsolidatedReportRow

def export_to_csv_stream(data: List[Union[ConsolidatedReportRow, Dict[str, Any]]]) -> bytes:
    """
    Exporta la lista de guías a un flujo de bytes CSV pura-de-dominio.
    Soporta instancias de ConsolidatedReportRow o diccionarios normalizados.
    """
    if not data:
        return b""
    
    headers = [
        "Guía", "Estado", "Entregado", "Fecha Entrega",
        "Destinatario", "Dirección", "Ciudad", "Último Evento", 
        "Mensajero/Op", "Contacto", "Excepciones", "Última Nota"
    ]
    
    output = io.StringIO()
    # Forzar saltos de línea normales para evitar dobles espaciados en Windows
    writer = csv.writer(output)
    writer.writerow(headers)
    
    for row in data:
        # Soporte para Dataclass o Dict
        if hasattr(row, 'waybill_no'):
            row_dict = {
                "waybill_no": getattr(row, 'waybill_no', ''),
                "status": getattr(row, 'status', ''),
                "is_delivered": getattr(row, 'is_delivered', False),
                "delivery_time": getattr(row, 'delivery_time', ''),
                "receiver": getattr(row, 'receiver', ''),
                "address": getattr(row, 'address', ''),
                "city": getattr(row, 'city', ''),
                "last_event_time": getattr(row, 'last_event_time', ''),
                "last_staff": getattr(row, 'last_staff', ''),
                "staff_contact": getattr(row, 'staff_contact', ''),
                "exceptions": getattr(row, 'exceptions', ''),
                "last_remark": getattr(row, 'last_remark', ''),
            }
        elif isinstance(row, dict):
            row_dict = row
        else:
            continue
            
        entregado_str = "SÍ" if row_dict.get("is_delivered") else "NO"
        writer.writerow([
            row_dict.get("waybill_no", ""),
            row_dict.get("status", ""),
            entregado_str, 
            row_dict.get("delivery_time", ""),
            row_dict.get("receiver", ""),
            row_dict.get("address", ""),
            row_dict.get("city", ""),
            row_dict.get("last_event_time", ""),
            row_dict.get("last_staff", ""),
            row_dict.get("staff_contact", ""),
            row_dict.get("exceptions", ""),
            row_dict.get("last_remark", ""),
        ])
        
    return output.getvalue().encode('utf-8')

def export_to_csv(data: List[Union[ConsolidatedReportRow, Dict[str, Any]]], filename: str):
    """Fallback para guardado físico en disco (CLI/Tests)"""
    csv_bytes = export_to_csv_stream(data)
    with open(filename, 'wb') as f:
        f.write(csv_bytes)
    print(f"Reporte exportado exitosamente a: {filename}")
