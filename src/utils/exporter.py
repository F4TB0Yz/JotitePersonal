import csv
from typing import List
from src.models.waybill import ConsolidatedReportRow

def export_to_csv(data: List[ConsolidatedReportRow], filename: str):
    if not data:
        return
    
    # Obtener cabeceras de los campos de la dataclass
    headers = [
        "Guía", "Estado", "Entregado", "Fecha Entrega",
        "Destinatario", "Dirección", "Ciudad", "Último Evento", 
        "Mensajero/Op", "Contacto", "Excepciones", "Última Nota"
    ]
    
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for row in data:
            entregado_str = "SÍ" if row.is_delivered else "NO"
            writer.writerow([
                row.waybill_no, row.status, entregado_str, 
                row.delivery_time,
                row.receiver, row.address, row.city, 
                row.last_event_time, row.last_staff, 
                row.staff_contact, row.exceptions, row.last_remark
            ])
    print(f"Reporte exportado exitosamente a: {filename}")
