"""LibEdge backend. Receives anonymous seat states from edge nodes, runs the context engine,
serves the admin dashboard and (optionally) answers students over Bluetooth LE."""
import asyncio, math, os, time, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import engine, sim
import mongo_sync
from layout import BY_ID, ZONES

NODE_KEY = os.getenv("NODE_KEY", "dev-node-key")
# Unknown seats are treated as unavailable until a simulator or edge node reports them.
STATE = {sid: "unknown" for sid in BY_ID}
NOISE = {k: float(v["noise"]) for k, v in ZONES.items()}
NODE_LAST_SEEN = {}
NODE_MODE = {floor: "edge" for floor in {seat.floor for seat in BY_ID.values()}}
log = logging.getLogger("libedge")

def answer(n: int) -> dict:
    return engine.compact(engine.recommend(STATE, NOISE, n), STATE)

@asynccontextmanager
async def lifespan(app):
    tasks = []
    mongo_uri = os.getenv("MONGODB_URI")
    simulate = os.getenv("SIMULATE", "1") == "1" and not mongo_uri
    if not simulate and NODE_KEY == "dev-node-key":
        raise RuntimeError("Set NODE_KEY to a private value before starting with real data sources")
    if simulate:
        sim.seed(STATE)
        for floor in NODE_MODE: NODE_MODE[floor] = "simulated"
        tasks.append(asyncio.create_task(sim.run(STATE)))
    mongo_client = None
    if mongo_uri:
        from pymongo import MongoClient
        for floor in NODE_MODE:
            NODE_MODE[floor] = "mongo"
        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        await asyncio.to_thread(mongo_client.admin.command, "ping")
        db = mongo_client[os.getenv("MONGODB_DATABASE", "libedge")]
        collection = db[os.getenv("MONGODB_COLLECTION", "floor_state")]
        interval = float(os.getenv("MONGODB_POLL_SECONDS", "2"))
        if interval <= 0:
            raise RuntimeError("MONGODB_POLL_SECONDS must be greater than zero")
        log.info("MongoDB connected; syncing %s.%s every %.1fs",
                 db.name, collection.name, interval)
        tasks.append(asyncio.create_task(mongo_sync.run(
            collection, STATE, NOISE, NODE_LAST_SEEN, NODE_MODE, interval
        )))
    if os.getenv("BLE") == "1":
        import ble_gateway; tasks.append(asyncio.create_task(ble_gateway.run(answer)))
    yield
    for t in tasks: t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    if mongo_client:
        await asyncio.to_thread(mongo_client.close)

app = FastAPI(title="LibEdge", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class EdgeUpdate(BaseModel):
    floor: int
    seats: dict[str, str]
    noise: dict[str, float] = Field(default_factory=dict)  # keys like "2-B"

@app.post("/api/edge/update")
def edge_update(u: EdgeUpdate, x_node_key: str = Header("")):
    if x_node_key != NODE_KEY: raise HTTPException(401, "bad node key")
    if u.floor not in {seat.floor for seat in BY_ID.values()}:
        raise HTTPException(400, "unknown floor")
    applied = 0
    for sid, st in u.seats.items():
        if sid in BY_ID and BY_ID[sid].floor == u.floor and st in ("empty", "occupied", "object"):
            STATE[sid] = st; applied += 1
    if applied == 0:
        raise HTTPException(400, "update contains no valid seat states for this floor")
    for key, db in u.noise.items():
        try:
            f, z = key.split("-", 1)
            zone = (int(f), z)
        except (ValueError, AttributeError):
            continue
        if zone in NOISE and math.isfinite(db) and 0 <= db <= 150:
            NOISE[zone] = db
    NODE_LAST_SEEN[u.floor] = time.time()
    NODE_MODE[u.floor] = "edge"
    return {"applied": applied}

def current_state():
    result = engine.summary(STATE, NOISE)
    now = time.time()
    result["nodes"] = [
        {"floor": floor, "mode": NODE_MODE[floor], "last_seen": NODE_LAST_SEEN.get(floor),
         "age_seconds": round(now - NODE_LAST_SEEN[floor]) if floor in NODE_LAST_SEEN else None}
        for floor in sorted({seat.floor for seat in BY_ID.values()})
    ]
    return result

@app.get("/api/state")
def state(): return current_state()

@app.get("/api/recommend")          # dev/demo path; students normally use Bluetooth
def recommend(group: int = 2): return answer(max(1, min(12, group)))

@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    try:
        while True:
            await sock.send_json(current_state()); await asyncio.sleep(2)
    except WebSocketDisconnect: pass
