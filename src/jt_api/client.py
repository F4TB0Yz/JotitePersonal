import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import ConfigORM
from src.domain.exceptions import APIError

_REQUEST_TIMEOUT = (10, 30)  # (connect, read) en segundos

_retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[502, 503, 504],
    allowed_methods=["POST", "GET"],
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retry_strategy, pool_connections=10, pool_maxsize=20)

class JTClient:
    def __init__(self, config: dict):
        self.config = config

        auth_token = self.config.get("authToken", "")
        
        self.base_url = self.config.get("baseUrl", "https://gw.jtexpress.co/operatingplatform")
        self.network_base_url = "https://gw.jtexpress.co/networkmanagement"
        self.busdicator_base_url = "https://gw.jtexpress.co/busdicator"
        self.servicequality_base_url = "https://gw.jtexpress.co/servicequality"
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "authToken": auth_token,
            "lang": self.config.get("lang", "es"),
            "langType": self.config.get("lang", "es"),
            "routeName": "trackingExpress",
            "timezone": self.config.get("timezone", "America/Bogota"),
            "Origin": "https://jms.jtexpress.co",
            "Referer": "https://jms.jtexpress.co/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        }

        self.session = requests.Session()
        self.session.mount("https://", _adapter)
        self.session.mount("http://", _adapter)
        self.session.headers.update(self.headers)

    def _post(self, endpoint, data, base=None, extra_headers=None):
        base_url = base if base else self.base_url
        url = f"{base_url}{endpoint}"
        
        request_headers = self.headers.copy()
        if extra_headers:
            request_headers.update(extra_headers)
            
        try:
            response = self.session.post(url, headers=request_headers, json=data, timeout=_REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if e.response is not None else None
            raise APIError(message=str(e), status_code=status_code)

    def get_order_detail(self, waybill_no):
        payload = {
            "waybillNo": waybill_no,
            "countryId": self.config.get("countryId", "1")
        }
        return self._post("/order/getOrderDetail", payload)

    def get_tracking_list(self, waybill_no):
        payload = {
            "keywordList": [waybill_no],
            "trackingTypeEnum": "WAYBILL",
            "countryId": self.config.get("countryId", "1")
        }
        return self._post("/podTracking/inner/query/keywordList", payload)

    def get_abnormal_list(self, waybill_no):
        payload = {
            "current": 1,
            "size": 100,
            "waybillId": waybill_no,
            "countryId": self.config.get("countryId", "1")
        }
        return self._post("/abnormalPieceScanList/pageList", payload)

    def search_messengers(self, account_name, network_id=1009):
        payload = {
            "accountName": account_name,
            "current": 1,
            "size": 50,
            "countryId": self.config.get("countryId", "1")
        }
        if network_id is not None:
            payload["networkId"] = network_id
        return self._post(
            "/spmSettlementRelationship/list",
            payload,
            base=self.network_base_url,
            extra_headers={"routeName": "CollectUser"}
        )

    def get_messenger_metrics(self, account_code, network_code, start_time, end_time):
        payload = {
            "current": 1,
            "size": 20,
            "dataType": "net",
            "startTime": start_time,
            "endTime": end_time,
            "settlementObjectCode": [account_code],
            "dispatchNetworkCode": [network_code],
            "dispatchFinanceCode": "R00001",
            "countryId": self.config.get("countryId", "1")
        }
        return self._post(
            "/bigdataReport/detail/network_ecology_staff",
            payload,
            base=self.busdicator_base_url,
            extra_headers={"routeName": "CollectUser"}
        )

    def get_messenger_metrics_sum(self, account_code, network_code, start_time, end_time):
        payload = {
            "current": 1,
            "size": 20,
            "dataType": "net",
            "startTime": start_time,
            "endTime": end_time,
            "settlementObjectCode": [account_code],
            "dispatchNetworkCode": [network_code],
            "dispatchFinanceCode": "R00001",
            "countryId": self.config.get("countryId", "1")
        }
        return self._post(
            "/bigdataReport/detail/network_ecology_staff_sum",
            payload,
            base=self.busdicator_base_url,
            extra_headers={"routeName": "CollectUser"}
        )

    def get_network_staff_daily(self, network_code, start_time, end_time, finance_code="R00001", page_size=100):
        """Fetch all dispatch staff records for a network on a date range, auto-paginating."""
        all_records = []
        page = 1
        safe_size = max(50, min(page_size, 200))

        while True:
            payload = {
                "current": page,
                "size": safe_size,
                "dataType": "net",
                "startTime": start_time,
                "endTime": end_time,
                "dispatchNetworkCode": [network_code],
                "dispatchFinanceCode": finance_code,
                "countryId": self.config.get("countryId", "1"),
            }
            response = self._post(
                "/bigdataReport/detail/network_ecology_staff",
                payload,
                base=self.busdicator_base_url,
                extra_headers={"routeName": "CollectUser"},
            )
            if response.get("code") != 1:
                break
            data = response.get("data", {}) or {}
            records = data.get("records", []) or []
            all_records.extend(records)
            total = data.get("total", 0) or 0
            if not records or len(all_records) >= total:
                break
            page += 1

        return all_records

    def get_messenger_waybills_detail(self, account_code, network_code, start_time, end_time, current=1, size=500):
        payload = {
            "current": current,
            "size": size,
            "dispatchStaffCode": [account_code],
            "settlementObjectCode": [account_code],
            "dispatchNetworkCode": [network_code],
            "dispatchFinanceCode": "R00001",
            "startTime": start_time,
            "endTime": end_time,
            "countryId": self.config.get("countryId", "1")
        }
        return self._post(
            "/bigdataReport/detail/network_ecology_staff_detail",
            payload,
            base=self.busdicator_base_url,
            extra_headers={"routeName": "CollectUser"}
        )

    def get_all_messenger_waybills_detail(self, account_code, network_code, start_time, end_time, page_size=500, max_pages=20):
        all_records = []
        page = 1
        safe_page_size = max(50, min(page_size, 1000))
        safe_max_pages = max(1, min(max_pages, 100))

        while page <= safe_max_pages:
            response = self.get_messenger_waybills_detail(
                account_code,
                network_code,
                start_time,
                end_time,
                current=page,
                size=safe_page_size,
            )

            if response.get("code") != 1:
                break

            data = response.get("data") or {}
            records = data.get("records") or []
            all_records.extend(records)

            total = data.get("total")
            if isinstance(total, int) and total >= 0 and len(all_records) >= total:
                break

            if len(records) < safe_page_size:
                break

            page += 1

        return all_records

    def get_network_signing_detail(self, network_code, start_time, end_time, sign_type=0, current=1, size=2000):
        """
        Consulta guías a nivel de red (Punto).
        :param sign_type: 0 (No firmadas), 1 (Firmadas)
        """
        payload = {
            "current": current,
            "size": size,
            "networkCode": network_code,
            "startTime": start_time,
            "endTime": end_time,
            "signType": sign_type,
            "lostMark": "N",
            "countryId": self.config.get("countryId", "1")
        }
        return self._post(
            "/bigdataReport/detail/bis_network_today_sign_detail",
            payload,
            base=self.busdicator_base_url,
            extra_headers={"routeName": "CollectUser"}
        )

    def get_waybill_receiver_phone(self, waybill_numbers):
        if not waybill_numbers:
            return {"data": []}
        if isinstance(waybill_numbers, str):
            joined = waybill_numbers
        else:
            cleaned = [wb.strip() for wb in waybill_numbers if wb and wb.strip()]
            joined = ",".join(cleaned)
        if not joined:
            return {"data": []}
        url = f"{self.servicequality_base_url}/thirdService/waybill/commonWaybillListByWaybillNos/receiverPhone"
        headers = self.headers.copy()
        headers["routeName"] = "recordSheet"
        try:
            response = self.session.get(url, headers=headers, params={"waybillNos": joined}, timeout=_REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if e.response is not None else None
            raise APIError(message=str(e), status_code=status_code)

    def get_temu_monitor_summary(
        self,
        current=1,
        size=20,
        dimension_type=2,
        responsible_org_code="1025006",
        country_id=None
    ):
        payload = {
            "current": current,
            "size": size,
            "dimensionType": dimension_type,
            "responsibleOrgCode": responsible_org_code,
            "countryId": country_id or self.config.get("countryId", "1")
        }
        return self._post(
            "/bigdataReport/detail/opt_tracking_monitor_temu_count",
            payload,
            base=self.busdicator_base_url,
            extra_headers={"routeName": "TrackMonitorTemu|crisbiIndex"}
        )

    def get_temu_monitor_detail(
        self,
        over_time_types=None,
        query_type=3,
        duty_agent_code="R00001",
        duty_code="1025006",
        manager_code="108108",
        problem_operate_types=None,
        current=1,
        size=50,
        country_id=None
    ):
        if not over_time_types:
            over_time_types = ["72小时"]
        if problem_operate_types is None:
            problem_operate_types = [
                "快件揽收",
                "入仓扫描",
                "发件扫描",
                "到件扫描",
                "中心到件",
                "集货到件",
                "出仓扫描",
                "代理点收入扫描",
                "问题件扫描",
                "建包扫描",
                "转第三方"
            ]
        payload = {
            "current": current,
            "size": size,
            "queryType": query_type,
            "overTimeTypes": over_time_types,
            "dutyAgentCode": duty_agent_code,
            "dutyCode": duty_code,
            "problemOperateType": problem_operate_types,
            "managerCode": manager_code,
            "countryId": country_id or self.config.get("countryId", "1")
        }
        return self._post(
            "/bigdataReport/detail/opt_tracking_monitor_temu_detail",
            payload,
            base=self.busdicator_base_url,
            extra_headers={"routeName": "TrackMonitorTemu|crisbiIndex"}
        )

    def reprint_waybills(self, waybill_ids, bill_type="small"):
        if not waybill_ids:
            raise ValueError("Debe enviar al menos una guía")

        if isinstance(waybill_ids, str):
            cleaned_ids = [waybill_ids.strip()] if waybill_ids.strip() else []
        else:
            cleaned_ids = [str(item).strip() for item in waybill_ids if str(item).strip()]

        if not cleaned_ids:
            raise ValueError("No hay guías válidas para reimpresión")

        payload = {
            "billType": bill_type or "small",
            "waybillIds": cleaned_ids,
            "countryId": str(self.config.get("countryId", "1")),
        }

        return self._post(
            "/print/reprintWaybillsNew",
            payload,
            base=self.base_url,
            extra_headers={"routeName": "Centerforplay"},
        )

    def get_delivery_photos(self, waybill_no, scan_time, scan_by_code, img_type=2):
        payload = {
            "waybillNo": waybill_no,
            "scanTime": scan_time,
            "scanByCode": scan_by_code,
            "imgType": img_type,
            "countryId": self.config.get("countryId", "1"),
        }
        return self._post("/podTracking/img/path", payload)

