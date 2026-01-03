from dataclasses import dataclass
from datetime import timedelta
from multiprocessing import Process
from blockchain_server import INetAddress
from service_maker import (
    Service,
    ProcessGroup,
    event_handler,
    periodic,
    Networker,
    EventQueue,
)
from service_maker import MsgTo, marshaller
from service_maker.decorators import MsgFrom, request_handler
from service_maker.event_driven import PeerConnected


# ============
# Define DataTypes
# ============
@dataclass
class Frog(MsgTo):
    name: str
    say: str


@dataclass
class FrogMsg(MsgTo):
    heller: str


@dataclass
class FrogResponse(MsgTo):
    goodbyer: str


# ============
# Register Data Types
# ============
marshaller.register("frog", Frog)
marshaller.register("frog_msg", FrogMsg)
marshaller.register("frog_response", FrogResponse)


# ============
# Create handlers
# ============
@periodic("frog_periodic", timedelta(seconds=1))
async def frog_periodic(event_queue: EventQueue, broadcaster: Networker) -> None:
    frog = Frog("froggie", "ribbit")
    print("Sending Frog")
    event_queue.put(frog)


@event_handler("frog_handler", Frog)
async def frog_handler(frog: Frog, event_queue: EventQueue, broadcaster: Networker):
    print(f"Frog '{frog.name}' says {frog.say}")
    broadcaster.broadcast(FrogMsg("Networking is working!"))


@request_handler("frog_msg_handler", FrogMsg)
async def frog_msg_handler(
    frog: MsgFrom[FrogMsg],
    event_queue: EventQueue,
    broadcaster: Networker,
):
    print(frog.msg.heller)
    # broadcaster.send(frog.peer_id, FrogResponse("Goodbyer"))


# @request_handler("frog_response_handler", FrogResponse)
# async def frog_response_handler(
#     frog: MsgFrom[FrogResponse],
#     event_queue: EventQueue,
#     broadcaster: Networker,
# ):
#     print(frog.msg.goodbyer)


@event_handler("peer_connected_handler", PeerConnected)
async def peer_connected_handler(
    peer_connected: PeerConnected, event_queue: EventQueue, broadcaster: Networker
):
    print(
        f"Connected to peer {peer_connected.address} with id {peer_connected.peer_id}"
    )


# ============
# Use the handlers
# ============
def main() -> None:
    s1 = Service(
        config={
            "hello_world": ProcessGroup(
                frog_periodic, frog_handler, frog_msg_handler, peer_connected_handler
            )
        },
        debug=True,
        known_addresses=[INetAddress("127.0.0.1", 8081)],
    )
    s2 = Service(
        config={
            "hello_world": ProcessGroup(
                frog_periodic, frog_handler, frog_msg_handler, peer_connected_handler
            )
        },
        debug=True,
        addr=INetAddress("127.0.0.1", 8081),
    )
    s1.run()
    s2.run()
    s1.join()
    s2.join()


if __name__ == "__main__":
    main()
