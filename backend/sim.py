"""Stand-in for floors that have no camera yet. Seeds the demo scenario, then drifts slowly."""
import asyncio, random
from layout import SEATS

def seed(state):
    random.seed(7)
    for s in SEATS:
        if s.floor == 2 and s.zone == "B": state[s.id] = "empty"          # the roomy quiet block
        elif s.floor == 2: state[s.id] = "occupied" if random.random() < .6 else "empty"
        elif s.floor == 1: state[s.id] = "occupied" if (s.r + s.c) % 2 == 0 or random.random() < .15 else "empty"
        else: state[s.id] = "occupied" if s.c == 2 or random.random() < .1 else "empty"

async def run(state):
    movers = [s for s in SEATS if not (s.floor == 2 and s.zone == "B")]
    while True:
        await asyncio.sleep(3)
        for s in random.sample(movers, 2):
            state[s.id] = "empty" if state[s.id] != "empty" else "occupied"
