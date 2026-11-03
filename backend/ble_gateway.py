"""Bluetooth LE gateway. Phones talk to the library over BLE only - no mobile data, no Wi-Fi.
Service layout:  REQ (write)  {"g": 6}      student -> gateway
                 REC (read/notify) compact JSON  gateway -> student"""
import asyncio, json, logging
from bless import BlessServer, GATTCharacteristicProperties as P, GATTAttributePermissions as A

SERVICE = "6c1b0001-9a4e-4e0f-8d0a-5b1d2c3e4f50"
REQ = "6c1b0002-9a4e-4e0f-8d0a-5b1d2c3e4f50"
REC = "6c1b0003-9a4e-4e0f-8d0a-5b1d2c3e4f50"
log = logging.getLogger("libedge.ble")

async def run(recommend):
    server = BlessServer(name="LibEdge", loop=asyncio.get_running_loop())
    server.read_request_func = lambda c, **kw: c.value

    def on_write(char, value, **kw):
        try: n = max(1, min(12, int(json.loads(bytes(value))["g"])))
        except Exception: return log.warning("bad request ignored")
        server.get_characteristic(REC).value = bytearray(json.dumps(recommend(n), separators=(",", ":")).encode())
        server.update_value(SERVICE, REC)
        log.info("answered group of %d", n)
    server.write_request_func = on_write

    await server.add_new_service(SERVICE)
    await server.add_new_characteristic(SERVICE, REQ, P.write, None, A.writeable)
    await server.add_new_characteristic(SERVICE, REC, P.read | P.notify, bytearray(b"{}"), A.readable)
    await server.start()
    log.info("advertising as LibEdge")
    try:
        while True: await asyncio.sleep(3600)
    finally:
        await server.stop()
