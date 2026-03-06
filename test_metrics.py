import asyncio
from src.jt_api.client import JTClient

client = JTClient()
account_code = "10250060001"
network_code = "1025006"

# Same day
print("Detail:")
res1 = client.get_messenger_metrics(account_code, network_code, "2026-02-24 00:00:00", "2026-02-24 23:59:59")
print(res1)
print("\nSum:")
res2 = client.get_messenger_metrics_sum(account_code, network_code, "2026-02-24 00:00:00", "2026-02-24 23:59:59")
print(res2)
