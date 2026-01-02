from dataclasses import dataclass
from datetime import timedelta
from multiprocessing import Process
from blockchain_server import INetAddress
from service_maker import (
    Service,
    ProcessGroup,
    event_handler,
    periodic,
    Broadcaster,
    EventQueue,
)
from service_maker.event_driven import PeerConnected


@dataclass
class Frog:
    name: str
    say: str


@periodic("frog_periodic", timedelta(seconds=1))
async def frog_periodic(event_queue: EventQueue, broadcaster: Broadcaster) -> None:
    frog = Frog("froggie", "ribbit")
    print("Sending Frog")
    event_queue.put(frog)


@event_handler("frog_handler", Frog)
async def frog_handler(frog: Frog, event_queue: EventQueue, broadcaster: Broadcaster):
    print(f"Frog '{frog.name}' says {frog.say}")


@event_handler("peer_connected_handler", PeerConnected)
async def peer_connected_handler(
    peer_connected: PeerConnected, event_queue: EventQueue, broadcaster: Broadcaster
):
    print(
        f"Connected to peer {peer_connected.address} with id {peer_connected.peer_id}"
    )


def main() -> None:
    s1 = Service(
        config={"hello_world": ProcessGroup(frog_periodic, frog_handler)},
        debug=True,
        known_addresses=[INetAddress("127.0.0.1", 8081)],
    )
    s2 = Service(
        config={"hello_world": ProcessGroup(frog_periodic, frog_handler)},
        debug=True,
        addr=INetAddress("127.0.0.1", 8081),
    )
    s1.run()
    s2.run()
    s1.join()
    s2.join()


if __name__ == "__main__":
    main()
