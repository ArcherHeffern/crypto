from datetime import timedelta
from random import randint, sample
from typing import Optional
from event_driven import (
    Broadcaster,
    EventQueue,
    ProcessGroup,
    Responder,
    Service,
    ThreadGroup,
    event_handler,
    periodic,
    request_handler,
    worker,
)
from main import (
    ExternalGossip,
    ExternalSolution,
    InternalOverrideProcessing,
    InternalSolutionFound,
)


GOSSIP_SIZE = 3


@request_handler(ExternalGossip)
async def gossip_handler(
    gossip: ExternalGossip,
    event_queue: EventQueue,
    broadcaster: Broadcaster,
    responder: Responder,
):
    random_addresses = sample(list(broadcaster.get_connections()), GOSSIP_SIZE)
    broadcaster.add_connections(gossip.addresses)
    responder.respond(ExternalGossip(random_addresses))


@periodic(timedelta(minutes=1))
async def gossiper(event_queue: EventQueue, broadcaster: Broadcaster):
    broadcaster.broadcast(
        ExternalGossip(sample(list(broadcaster.get_connections()), GOSSIP_SIZE))
    )


@worker(listen_for=InternalOverrideProcessing)  # Run for a bit of work
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


@event_handler(InternalSolutionFound)
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
    broadcaster.broadcast(ExternalSolution(solution_found.solution))
    # Look at backlogged transactions for new problem
    new_problem = 1
    # Override processing
    event_queue.broadcast(InternalOverrideProcessing(new_problem))


@request_handler(ExternalSolution)
async def x_solution_found_handler(
    solution_found: ExternalSolution,
    event_queue: EventQueue,
    broadcaster: Broadcaster,
    responder: Responder,
):
    # If is valid solution
    ...
    # Append to blockchain
    ...
    event_queue.broadcast(InternalOverrideProcessing(solution_found.solution))
    broadcaster.broadcast(ExternalSolution(solution_found.solution))


s = Service(
    {
        "thread": ThreadGroup(
            gossip_handler, gossiper, i_solution_found_handler, x_solution_found_handler
        ),
        "workers": ProcessGroup(miner, miner),
    }
)
