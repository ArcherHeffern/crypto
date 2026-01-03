from dataclasses import dataclass
from datetime import timedelta
from random import randint, sample
from typing import Optional
from service_maker import (
    EventQueue,
    ProcessGroup,
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
from service_maker.decorators import Networker, Responder


@dataclass
class GossipRequest(MsgTo):
    addresses: list[INetAddress]


@dataclass
class GossipResponse(MsgTo):
    addresses: list[INetAddress]


@dataclass
class SolutionFoundRequest(MsgTo):
    solution: int


@dataclass
class SolutionFoundBroadcast(MsgTo):
    solution: int


GOSSIP_SIZE = 3


@request_handler("gossip_request_handler", GossipRequest)
async def gossip_request_handler(
    gossip: MsgFrom[GossipRequest],
    event_queue: EventQueue,
    broadcaster: Networker,
    responder: Responder,
):
    random_addresses = sample(list(broadcaster.get_addresses()), GOSSIP_SIZE)
    for address in gossip.msg.addresses:
        broadcaster.connect(address)
    responder.respond(GossipResponse(random_addresses))


@request_handler("gossip_response_handler", GossipResponse)
async def gossip_response_handler(
    gossip: MsgFrom[GossipResponse],
    event_queue: EventQueue,
    broadcaster: Networker,
    responder: Responder,
):
    for address in gossip.msg.addresses:
        broadcaster.connect(address)


@periodic("gossiper", timedelta(minutes=1))
async def gossiper(event_queue: EventQueue, broadcaster: Networker):
    broadcaster.broadcast(
        GossipResponse(sample(list(broadcaster.get_addresses()), GOSSIP_SIZE))
    )


@worker("miner", listen_for=InternalOverrideProcessing)  # Run for a bit of work
async def miner(
    listen_for: Optional[InternalOverrideProcessing],
    event_queue: EventQueue,
    _: Networker,
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
    broadcaster: Networker,
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
    solution_found: MsgFrom[SolutionFoundRequest],
    event_queue: EventQueue,
    broadcaster: Networker,
    responder: Responder,
):
    # If is valid solution
    ...
    # Append to blockchain
    ...
    # Broadcast solution
    event_queue.broadcast(InternalOverrideProcessing(solution_found.msg.solution))
    # Look at backlogged transactions for new problem
    new_problem = 1
    # Override processing


s = Service(
    {
        "thread": ThreadGroup(
            gossip_request_handler,
            gossip_response_handler,
            gossiper,
            i_solution_found_handler,
            x_solution_found_handler,
        ),
        "workers": ProcessGroup(miner, miner),
    }
)
