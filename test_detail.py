import asyncio
from src.jt_api.client import JTClient

client = JTClient()
account_code = "10250060001"
network_code = "1025006"

payload = {
    "current": 1,
    "size": 50,
    "dispatchStaffCode": [account_code],
    "settlementObjectCode": [account_code],
    "dispatchNetworkCode": [network_code],
    "dispatchFinanceCode": "R00001",
    "startTime": "2026-02-18 00:00:00",
    "endTime": "2026-02-18 23:59:59",
    "countryId": "1"
}

res = client._post(
    "/bigdataReport/detail/network_ecology_staff_detail",
    payload,
    base=client.busdicator_base_url,
    extra_headers={"routeName": "CollectUser"}
)
print(res)
