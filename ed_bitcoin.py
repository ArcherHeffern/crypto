from dataclasses import dataclass
from datetime import timedelta
from random import randint, sample
from typing import Optional
from service_maker import (
    Broadcaster,
    EventQueue,
    ProcessGroup,
    Responder,
    ThreadGroup,
    event_handler,
    periodic,
    request_handler,
    worker,
)
from blockchain_server import (
    INetAddress,
    InternalOverrideProcessing,
    InternalSolutionFound,
)
from service_maker import MsgFrom, MsgTo, Service


@dataclass
class GossipRequest(MsgFrom):
    addresses: list[INetAddress]


@dataclass
class GossipResponse(MsgTo):
    addresses: list[INetAddress]


@dataclass
class SolutionFoundRequest(MsgFrom):
    solution: int


@dataclass
class SolutionFoundBroadcast(MsgTo):
    solution: int


GOSSIP_SIZE = 3


@request_handler("gossip_handler", GossipRequest)
async def gossip_handler(
    gossip: GossipRequest,
    event_queue: EventQueue,
    broadcaster: Broadcaster,
    responder: Responder,
):
    random_addresses = sample(list(broadcaster.get_addresses()), GOSSIP_SIZE)
    for address in gossip.addresses:
        broadcaster.connect(address)
    responder.respond(GossipResponse(random_addresses))


@periodic("gossiper", timedelta(minutes=1))
async def gossiper(event_queue: EventQueue, broadcaster: Broadcaster):
    broadcaster.broadcast(
        GossipResponse(sample(list(broadcaster.get_addresses()), GOSSIP_SIZE))
    )


@worker("miner", listen_for=InternalOverrideProcessing)  # Run for a bit of work
async def miner(
    listen_for: Optional[InternalOverrideProcessing],
    event_queue: EventQueue,
    _: Broadcaster,
    state: dict,
):
    if listen_for:
        state["problem"] = listen_for.new_problem
    # Look for solution
    problem = state["problem"]
    for __ in range(1_000_000):
        solution_found = randint(0, 8)
        if solution_found:
            solution = randint(0, 32)
            event_queue.put(InternalSolutionFound("", solution))
            return


@event_handler("i_solution_found_handler", InternalSolutionFound)
async def i_solution_found_handler(
    solution_found: InternalSolutionFound,
    event_queue: EventQueue,
    broadcaster: Broadcaster,
):
    # Validate solution by index
    ...
    # Append to blockchain
    ...
    # Broadcast solution
    broadcaster.broadcast(SolutionFoundBroadcast(solution_found.solution))
    # Look at backlogged transactions for new problem
    new_problem = 1
    # Override processing
    event_queue.broadcast(InternalOverrideProcessing(new_problem))


@request_handler("x_solution_found_handler", SolutionFoundRequest)
async def x_solution_found_handler(
    solution_found: SolutionFoundRequest,
    event_queue: EventQueue,
    broadcaster: Broadcaster,
    responder: Responder,
):
    # If is valid solution
    ...
    # Append to blockchain
    ...
    # Broadcast solution
    event_queue.broadcast(InternalOverrideProcessing(solution_found.solution))
    # Look at backlogged transactions for new problem
    new_problem = 1
    # Override processing
    broadcaster.broadcast(SolutionFoundBroadcast(new_problem))


s = Service(
    {
        "thread": ThreadGroup(
            gossip_handler, gossiper, i_solution_found_handler, x_solution_found_handler
        ),
        "workers": ProcessGroup(miner, miner),
    }
)
