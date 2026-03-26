import pytest
from src.models.waybill import TrackingEvent
from src.domain.specifications.pending_waybill_spec import ExcludeRulesComposite
from src.domain.enums.waybill_enums import WaybillStatusEnum

def test_terminal_status_rule_excludes_delivered():
    """Verifica que TerminalStatusRule excluya paquetes entregados."""
    spec = ExcludeRulesComposite("Cund-Punto6")
    events = [
        TrackingEvent(time="now", type_name="Paquete firmado", status="Entregado", network_name="Cund-Punto6", code=100)
    ]
    # should_exclude debe retornar True para paquetes terminales
    assert spec.should_exclude(events) is True

def test_carga_expedicion_rule_excludes_dispatched_from_target():
    """Verifica que CargaExpedicionRule excluya paquetes despachados desde la red objetivo."""
    target = "Cund-Punto6"
    spec = ExcludeRulesComposite(target)
    events = [
        TrackingEvent(time="now", type_name="Carga y expedición", network_name=target, code=1),
        TrackingEvent(time="past", type_name="Arribo a PDV", network_name=target, code=20)
    ]
    assert spec.should_exclude(events) is True

def test_different_network_rule_excludes_outside_jurisdiction():
    """Verifica que DifferentNetworkRule excluya si el último evento es en otra red."""
    target = "Cund-Punto6"
    spec = ExcludeRulesComposite(target)
    events = [
        TrackingEvent(time="now", type_name="Arribo a PDV", network_name="Bogota.sc", scan_network_id="1001"),
        TrackingEvent(time="past", type_name="Descarga TR1/2", network_name=target, scan_network_id="1009")
    ]
    # scan_network_id "1001" != "1009"
    assert spec.should_exclude(events) is True

def test_no_exclusion_for_pending_at_target():
    """Verifica que un paquete sea PENDIENTE (no excluido) si tiene arribo y nada más."""
    target = "Cund-Punto6"
    spec = ExcludeRulesComposite(target)
    events = [
        TrackingEvent(time="now", type_name="Arribo a PDV", network_name=target, scan_network_id="1009", code=20)
    ]
    assert spec.should_exclude(events) is False
