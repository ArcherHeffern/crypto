from dataclasses import dataclass
from datetime import timedelta
from random import randint, sample
from typing import Optional
from p2p_framework import (
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
    InternalSolutionFound,
)
from p2p_framework import MsgFrom, MsgTo, Service, Networker
from p2p_framework import MsgTo, marshaller


@dataclass
class GossipRequest(MsgTo):
    addresses: list[INetAddress]


marshaller.register("gossip_request", GossipRequest)


@dataclass
class GossipResponse(MsgTo):
    addresses: list[INetAddress]


marshaller.register("gossip_response", GossipRequest)


@dataclass
class SolutionFoundRequest(MsgTo):
    solution: int


marshaller.register("solution_found_request", SolutionFoundRequest)


@dataclass
class SolutionFoundBroadcast(MsgTo):
    solution: int


marshaller.register("solution_found_broadcast", SolutionFoundBroadcast)


@dataclass
class SolutionFoundEvent(MsgTo):
    solution: int


marshaller.register("solution_found_event", SolutionFoundEvent)


@dataclass
class OverrideProcessingEvent(MsgTo):
    new_problem: int


marshaller.register("override_processing_event", OverrideProcessingEvent)

GOSSIP_SIZE = 3


@request_handler("gossip_request_handler", GossipRequest)
async def gossip_request_handler(
    gossip: MsgFrom[GossipRequest],
    event_queue: EventQueue,
    broadcaster: Networker,
):
    random_addresses = sample(list(broadcaster.get_addresses()), GOSSIP_SIZE)
    for address in gossip.msg.addresses:
        broadcaster.connect(address)
    broadcaster.send(gossip.peer_id, GossipResponse(random_addresses))


@request_handler("gossip_response_handler", GossipResponse)
async def gossip_response_handler(
    gossip: MsgFrom[GossipResponse],
    event_queue: EventQueue,
    broadcaster: Networker,
):
    for address in gossip.msg.addresses:
        broadcaster.connect(address)


@periodic("gossiper", timedelta(minutes=1))
async def gossiper(event_queue: EventQueue, broadcaster: Networker):
    broadcaster.broadcast(
        GossipResponse(sample(list(broadcaster.get_addresses()), GOSSIP_SIZE))
    )


@worker("miner", listen_for=OverrideProcessingEvent)  # Run for a bit of work
async def miner(
    listen_for: Optional[OverrideProcessingEvent],
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


@event_handler("i_solution_found_handler", SolutionFoundEvent)
async def i_solution_found_handler(
    solution_found: SolutionFoundEvent,
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
    event_queue.broadcast(OverrideProcessingEvent(new_problem))


@request_handler("x_solution_found_handler", SolutionFoundRequest)
async def x_solution_found_handler(
    solution_found: MsgFrom[SolutionFoundRequest],
    event_queue: EventQueue,
    broadcaster: Networker,
):
    # If is valid solution
    ...
    # Append to blockchain
    ...
    # Broadcast solution
    broadcaster.broadcast(
        SolutionFoundBroadcast(solution_found.msg.solution),
        exclude_peer_ids=[solution_found.peer_id],
    )
    # Look at backlogged transactions for new problem
    new_problem = 1
    # Override processing
    event_queue.broadcast(OverrideProcessingEvent(solution_found.msg.solution))


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
