import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.web_ui import security
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.jt_api.client import JTClient
from src.services.report_service import ReportService
from src.services.notification_service import notification_manager

router = APIRouter(tags=["WebSockets"])

@router.websocket("/ws/process")
async def websocket_process(websocket: WebSocket):
    if not security._is_authenticated_websocket(websocket):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    
    try:
        data = await websocket.receive_text()
        request_data = json.loads(data)
        waybills = request_data.get("waybills", [])
        
        if not waybills:
            await websocket.send_json({"type": "error", "message": "No se proporcionaron guías."})
            await websocket.close()
            return

        try:
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            service = ReportService(client, TrackingEventRepository(SessionLocal()))
        except Exception as e:
            await websocket.send_json({"type": "error", "message": f"Error inicializando cliente: {e}"})
            await websocket.close()
            return

        for wb in waybills:
            wb = wb.strip()
            if not wb:
                continue
            try:
                data = await asyncio.to_thread(service.get_consolidated_data, wb)
                result_dict = {
                    "waybill_no": data.waybill_no,
                    "status": data.status,
                    "order_source": data.order_source,
                    "sender": data.sender,
                    "receiver": data.receiver,
                    "city": data.city,
                    "weight": data.weight,
                    "last_event_time": data.last_event_time,
                    "last_network": data.last_network,
                    "last_staff": data.last_staff,
                    "staff_contact": data.staff_contact,
                    "is_delivered": data.is_delivered,
                    "arrival_punto6_time": data.arrival_punto6_time,
                    "delivery_time": data.delivery_time,
                    "address": data.address,
                    "exceptions": data.exceptions,
                    "last_remark": data.last_remark
                }
                await websocket.send_json({"type": "result", "data": result_dict})
            except Exception as e:
                await websocket.send_json({
                    "type": "result", 
                    "data": {
                        "waybill_no": wb,
                        "status": "Error",
                        "is_delivered": False,
                        "exceptions": str(e)
                    }
                })
        
        await websocket.send_json({"type": "done"})
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    if not security._is_authenticated_websocket(websocket):
        await websocket.close(code=1008)
        return

    await notification_manager.connect(websocket)
    heartbeat_task = None
    try:
        async def heartbeat():
            while True:
                await asyncio.sleep(20)
                await websocket.send_json({"type": "heartbeat", "payload": {"ok": True}})

        heartbeat_task = asyncio.create_task(heartbeat())

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        await notification_manager.disconnect(websocket)
