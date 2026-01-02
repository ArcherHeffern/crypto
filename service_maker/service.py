import asyncio
import contextlib
from dataclasses import dataclass
from datetime import timedelta
from asyncio import (
    StreamReader,
    StreamWriter,
    Task,
    create_task,
    open_connection,
    run,
    start_server,
)
from multiprocessing import Process, Queue
from time import sleep
from typing import Callable, NoReturn, Optional

from blockchain_server import INetAddress
from .decorators import (
    Broadcast,
    Broadcaster,
    Connect,
    Disconnect,
    EventHandler,
    EventHandlerAndData,
    Handler,
    MsgFrom,
    MsgTo,
    NetworkEvent,
    PeerId,
    PeriodicHandlerAndData,
    Send,
)
from .event_driven import (
    EventQueue,
    PeerDisconnected,
)
from .service_config import ProcessGroup, ThreadGroup

MAPPINGS: dict[str, Handler] = {}
from marshall import DataclassMarshaller

marshaller = DataclassMarshaller[MsgTo]()


def periodic_function(
    func_name: str,
    dt: timedelta,
    event_queue: EventQueue,
    network_queue: Queue,
) -> None:
    from .service import MAPPINGS

    func: PeriodicHandler = MAPPINGS[func_name]  # type: ignore

    async def f() -> NoReturn:
        while True:
            await asyncio.sleep(dt.total_seconds())
            await func(event_queue, Broadcaster(network_queue))

    run(f())


def event_handler_function(
    func_name: str,
    q: Queue,
    event_queue: EventQueue,
    network_queue: Queue,
):
    from .service import MAPPINGS

    func: EventHandler = MAPPINGS[func_name]  # type: ignore

    async def f() -> NoReturn:
        while True:
            try:
                v = q.get(timeout=0.2)
                await func(v, event_queue, Broadcaster(network_queue))
            except:
                ...
            sleep(0.1)

    run(f())


@dataclass
class Connection:
    peer_id: PeerId
    address: INetAddress
    reader: StreamReader
    writer: StreamWriter
    read_task: Task


def network_handler_function(
    group_data: dict[type, dict[str, Queue]],
    outbound_queue: Queue[NetworkEvent],
    server_address: INetAddress,
    known_addresses: list[INetAddress],
):
    for known_address in known_addresses:
        outbound_queue.put(Connect(known_address))

    async def f() -> NoReturn:
        peer_id_to_connection: dict[PeerId, Connection] = {}
        address_to_peer_id: dict[INetAddress, PeerId] = {}
        nxt_peer_id = 1
        inbound_queue = asyncio.Queue[MsgFrom]()
        event_queue = asyncio.Queue()

        async def disconnect_peer(peer_id: PeerId) -> None:
            conn = peer_id_to_connection.get(peer_id)
            if not conn:
                return
            address = conn.address

            # cancel read task if it's not this task
            if conn.read_task is not asyncio.current_task():
                conn.read_task.cancel()
                with contextlib.suppress(Exception):
                    await conn.read_task

            conn.writer.close()
            with contextlib.suppress(Exception):
                await conn.writer.wait_closed()

            peer_id_to_connection.pop(peer_id, None)
            address_to_peer_id.pop(address, None)

        async def reader(peer_id: PeerId) -> None:
            """Read bytes/messages from a peer and emit events back to main."""
            conn = peer_id_to_connection[peer_id]
            r = conn.reader
            try:
                while True:
                    o = await marshaller.load_stream(r)
                    if o:
                        await inbound_queue.put(MsgFrom(peer_id=peer_id, msg=o))
            finally:
                # treat EOF as disconnect
                await event_queue.put(
                    PeerDisconnected(
                        peer_id=peer_id, address=conn.address, reason="eof"
                    )
                )
                await disconnect_peer(peer_id)

        async def cb(r: StreamReader, w: StreamWriter):
            nonlocal nxt_peer_id
            peername = w.get_extra_info("peername")
            if not peername:
                w.close()
                await w.wait_closed()
                return
            host, port = peername[0], peername[1]
            address = INetAddress(host, port)
            if address not in address_to_peer_id:
                peer_id = nxt_peer_id
                nxt_peer_id += 1

                t = create_task(reader(peer_id))
                peer_id_to_connection[peer_id] = Connection(peer_id, address, r, w, t)
                address_to_peer_id[address] = peer_id

        # Waits for connections and adds them to our connection data structures
        s = start_server(cb, server_address.host, server_address.port)
        broadcaster = Broadcaster(outbound_queue)

        while True:
            # Event Handler
            if not outbound_queue.empty():
                event = outbound_queue.get()
                match event:
                    case Connect():
                        if event.address not in address_to_peer_id:
                            r, w = await open_connection(
                                event.address.host, event.address.port
                            )
                            peer_id = nxt_peer_id
                            nxt_peer_id += 1
                            t = create_task(reader(peer_id))
                            peer_id_to_connection[peer_id] = Connection(
                                peer_id, event.address, r, w, t
                            )
                            address_to_peer_id[event.address] = peer_id
                    case Disconnect():
                        if event.peer_id in peer_id_to_connection:
                            connection = peer_id_to_connection[event.peer_id]
                            await disconnect_peer(connection.peer_id)
                    case Broadcast():
                        for peer_id, connection in peer_id_to_connection.items():
                            if (
                                event.exclude_peer_ids
                                and peer_id not in event.exclude_peer_ids
                            ):
                                marshaller.dump_stream(event.msg, connection.writer)
                    case Send():
                        marshaller.dump_stream(
                            event.msg, peer_id_to_connection[event.peer_id].writer
                        )
                    case _:
                        raise NotImplementedError(
                            f"Type {type(event)} is not supported"
                        )
            await asyncio.sleep(0.1)
            # Handle inbound_queue event dispatching
            if not inbound_queue.empty():
                event = await inbound_queue.get()
                t = type(event.msg)
                if t in group_data:
                    for q in group_data[t].values():
                        q.put(event)

            # Handle event_queue event dispatching

    run(f())


class Service:
    def __init__(
        self,
        config: dict[str, ThreadGroup | ProcessGroup],
        debug: bool = False,
        addr: INetAddress = INetAddress("127.0.0.1", 8080),
        known_addresses: Optional[list[INetAddress]] = None,
    ):
        self.config = config
        self.debug = debug
        self.addr = addr
        self.known_addresses = known_addresses
        self.processes: list[Process] = []

    def log(self, msg: str):
        if self.debug:
            print(msg)

    def run(self):
        # Create object of all types and what queues they map to
        # EventQueue will handle the routing by type and possibly duplicating the request if its a broadcast
        # Create processes for all queues

        # type -> handler_name -> queue
        group_data: dict[type, dict[str, Queue]] = {}
        event_queue = EventQueue(group_data)
        network_queue = Queue()
        processes_to_run: list[tuple[Callable, tuple]] = []
        for group_name, group in self.config.items():
            match group:
                # Register the event listeners
                # Start the servers
                # Start periodic tasks
                case ThreadGroup():
                    print(f"Created thread group {group_name}")
                case ProcessGroup():
                    for process in group.processes:
                        match process:
                            case PeriodicHandlerAndData():
                                target = periodic_function
                                args = (
                                    process.name,
                                    process.dt,
                                    event_queue,
                                    network_queue,
                                )
                                processes_to_run.append((target, args))
                            case EventHandlerAndData():
                                if not group_data.get(process.t):
                                    group_data[process.t] = {}
                                this_q = Queue()
                                group_data[process.t][process.name] = this_q
                                target = event_handler_function
                                args = (
                                    process.name,
                                    this_q,
                                    event_queue,
                                    network_queue,
                                )
                                processes_to_run.append((target, args))
                            case _:
                                raise NotImplementedError(
                                    f"{type(process)} not implemented"
                                )
        processes_to_run.append(
            (
                network_handler_function,
                (group_data, network_queue, self.addr),
            )
        )
        for target, args in processes_to_run:
            p = Process(
                target=target,
                args=(*args,),
                daemon=True,
            )
            p.start()
            self.processes.append(p)
            self.log(f"Started {args[0]}")

    def join(self):
        for p in self.processes:
            p.join()
