import pytest
from src.models.waybill import TrackingEvent, is_pending_at_network

def test_waybill_is_pending_on_valid_inclusion():
    """Validates that a package with an arrival event at the target network is pending."""
    events = [
        TrackingEvent(time="2024-03-26 10:00", type_name="Arribo a PDV", network_name="Cund-Punto6", code=20)
    ]
    assert is_pending_at_network(events, "Cund-Punto6") is True

def test_waybill_is_not_pending_without_inclusion():
    """Validates that a package without an arrival event is NOT pending."""
    events = [
        TrackingEvent(time="2024-03-26 10:00", type_name="Otras gestiones", network_name="Cund-Punto6", code=999)
    ]
    assert is_pending_at_network(events, "Cund-Punto6") is False

def test_waybill_is_not_pending_when_delivered():
    """Validates that a delivered package (code 100) is NOT pending."""
    events = [
        TrackingEvent(time="2024-03-26 10:00", type_name="Arribo a PDV", network_name="Cund-Punto6", code=20),
        TrackingEvent(time="2024-03-26 11:00", type_name="Paquete firmado", network_name="Cund-Punto6", code=100)
    ]
    assert is_pending_at_network(events, "Cund-Punto6") is False

def test_waybill_is_not_pending_when_dispatched_out_of_target_network():
    """
    Validates that a package dispatched from the target network (code 1) is NOT pending.
    Scenario: Carga y expedición desde Cund-Punto6 hacia Bogota.sc.
    """
    events = [
        TrackingEvent(time="2024-03-26 10:00", type_name="Descarga TR1/2", network_name="Cund-Punto6", code=2),
        TrackingEvent(time="2024-03-26 12:00", type_name="Carga y expedición", network_name="Cund-Punto6", code=1)
    ]
    # Even though it has an inclusion event, the exclusion event (dispatch from same network) takes precedence.
    assert is_pending_at_network(events, "Cund-Punto6") is False

def test_waybill_is_not_pending_on_return_codes():
    """Validates that return codes 170 and 172 return False."""
    # Test for 170
    events_170 = [
        TrackingEvent(time="2024-03-26 10:00", type_name="Arribo a PDV", network_name="Cund-Punto6", code=20),
        TrackingEvent(time="2024-03-26 11:00", type_name="Registro de devolución", network_name="Cund-Punto6", code=170)
    ]
    assert is_pending_at_network(events_170, "Cund-Punto6") is False

    # Test for 172
    events_172 = [
        TrackingEvent(time="2024-03-26 10:00", type_name="Arribo a PDV", network_name="Cund-Punto6", code=20),
        TrackingEvent(time="2024-03-26 11:00", type_name="Escaneo de devolución", network_name="Cund-Punto6", code=172)
    ]
    assert is_pending_at_network(events_172, "Cund-Punto6") is False

def test_waybill_is_pending_if_dispatched_at_different_network():
    """
    Validates that a dispatch event at a DIFFERENT network does not exclude it from the target network 
    (unless we have an exclusion event at the target network later).
    Wait, the rule says "UNAMENTE si cumple con tener la entrada al nodo y NO tener ningún evento de salida o cierre".
    If it arrived at Punto 6, and then we see a dispatch from Bogota, it still means it left Bogota, but 
    did it leave Punto 6? 
    Usually, events follow a sequence. If it's in Punto 6 and then Bogota, it must have left Punto 6.
    However, the rule specifically says "scanNetworkName == target_network" for the displacement.
    """
    events = [
        TrackingEvent(time="2024-03-26 10:00", type_name="Arribo a PDV", network_name="Cund-Punto6", code=20),
        TrackingEvent(time="2024-03-26 12:00", type_name="Carga y expedición", network_name="Otra-Red", code=1)
    ]
    # According to the strict rule: code == 1 AND network == target_network is the exclusion.
    # Since this dispatch is from "Otra-Red", it doesn't trigger the "Exit from target" rule.
    # But wait, logic-wise, if it's in Otra-Red, it's not in Punto6 anymore.
    # But the user's pseudo-code was: (str(e.get("code")) == "1" and e.get("scanNetworkName") == target_network)
    assert is_pending_at_network(events, "Cund-Punto6") is True
