from abc import ABC
from inspect import signature
from dataclasses import dataclass, asdict, is_dataclass
from json import dumps, loads
from multiprocessing import Process, Queue as MultiProcessQueue
import time
from typing import (
    Any,
    Awaitable,
    Iterable,
    Optional,
    ClassVar,
    Type,
    get_args,
    get_origin,
)
from random import randint, sample
from asyncio import (
    Event,
    create_task,
    gather,
    sleep,
    start_server,
    StreamReader,
    StreamWriter,
    open_connection,
    Queue,
    run,
)
from bitcoin import Block
from marshall import DataclassMarshaller


# Task : Allows me to group things together or just run something in the background
# gather and TaskGroup can be used interchangbly
# asyncio.socket_server & asyncio.open_connection are 2 ends of the same coin.


@dataclass
class ServerHandle:
    addr: INetAddress
    reader: StreamReader
    writer: StreamWriter
    q: Queue


@dataclass
class MinerHandle:
    process: Process
    q2m: MultiProcessQueue[MinerOp]


@dataclass(frozen=True)
class INetAddress:
    host: str
    port: int


# ============
# Inter-Server Messages
# ============


@dataclass()
class InterServerMessage(ABC): ...


@dataclass
class SolutionFound(InterServerMessage):
    solution: int


@dataclass
class Gossip(InterServerMessage):
    addresses: list[INetAddress]


# ============
# Server Operations
# ============
class ControllerOp(ABC):
    # Base class for operations sent to the controller
    ...


class BroadcasterOp(ABC):
    # Base class for operations sent to the broadcaster
    ...


class ServerOp(ABC):
    # Base class for operations sent to the server
    ...


class MinerOp(ABC):
    # Base class for operations sent to a miner
    ...


# @dataclass
# class GossipOp(ControllerOp):
#     server_addresses: list[INetAddress]


@dataclass
class ToldSolutionOp(ControllerOp):
    solution: int


@dataclass
class FoundSolutionOp(ControllerOp, BroadcasterOp):
    miner_id: str
    solution: int


@dataclass
class OverrideProcessing(MinerOp):
    new_problem: int


class BlockchainServer:
    """
    Pushing:
    -> Send via broadcaster and get via server
    - Solution


    Pulling:
    -> Send and wait for response in broadcaster
    - Gossip protocol

    """

    def __init__(self, other_server_addresses: list[INetAddress], id: int):
        if id <= 8000:
            raise ValueError(f"Expected id >= 8000 but found '{id}'")
        # self.blockchain: list[Block] = []
        self.id = id
        self.blockchain: list[int] = []
        self.sync_event = Event()
        self.workers = 2
        self.other_server_addresses: list[INetAddress] = other_server_addresses
        self.gossip_size = 3

        self.other_servers: dict[INetAddress, Optional[ServerHandle]] = {
            address: None for address in self.other_server_addresses
        }

        self.m = DataclassMarshaller[InterServerMessage]()
        self.m.register("solution_found", SolutionFound)
        self.m.register("gossip", Gossip)
        self.m.register("inet_address", INetAddress)
        # Asyncio Concurrency
        self.q2controller: Queue[ControllerOp] = Queue()
        self.q2broadcaster: Queue[BroadcasterOp] = Queue()
        self.q2server: Queue[ServerOp] = Queue()

        # Multiprocessing Concurrency
        # self.update_event = Event()
        # self.shutdown_event = Event()
        self.miners: dict[str, MinerHandle] = {}
        self.q2c: MultiProcessQueue[ControllerOp] = MultiProcessQueue()

    async def run(self) -> bool:
        for i in range(self.workers):
            q2m = MultiProcessQueue()
            miner_id = f"{self.id}:{i}"
            p = Process(target=self.miner, args=(miner_id, q2m, self.q2c), daemon=True)
            p.start()
            ph = MinerHandle(p, q2m)
            self.miners[miner_id] = ph

        server = await start_server(
            self.srv(), "127.0.0.1", self.id
        )  # TODO: Does this need to be passed the self paramterer explicitly?
        b_task = create_task(self.broadcaster())
        c_task = create_task(self.controller())
        async with server:
            print("Server Forever")
            await server.serve_forever()

        return True

    async def broadcaster(self):
        self.log("Starting broadcaster")
        other_servers = self.other_servers
        while True:
            # Gossip Protocol
            random_servers = (
                sample(list(other_servers.values()), k=self.gossip_size)
                if len(other_servers) >= self.gossip_size
                else list(self.other_servers.values())
            )
            gossip = Gossip(addresses=[s.addr for s in random_servers if s])
            gossip_msg = self.m.dumps(gossip).encode()
            awaitables: list[Awaitable] = []
            for random_server in random_servers:
                if random_server is None:
                    continue
                random_server.writer.write(gossip_msg)
                awaitables.append(random_server.reader.readuntil(b"\n"))
            print("BEFORE ----------")
            responses: list[bytes] = await gather(
                *awaitables
            )  # TODO: Fix this bullshit from hanging.
            print("AFTER -----------")
            for response in responses:
                gossip_res = self.m.loads(response.decode())
                if not isinstance(gossip_res, Gossip):
                    continue
                for address in gossip_res.addresses:
                    if address not in other_servers:
                        other_servers[address] = None
                        print(f"Found new address {address}")

            await sleep(0.1)

            # Connect to all servers
            for address, server_handle in other_servers.items():
                if server_handle is not None:
                    continue
                r, w = await open_connection(address.host, address.port)
                self.log(f"Connected to {address.host}:{address.port}")
                other_servers[address] = ServerHandle(address, r, w, Queue())
            await sleep(0.1)

            # Handle Events to Broadcaster
            if not self.q2broadcaster.empty():
                event = self.q2broadcaster.get_nowait()
                match event:
                    case FoundSolutionOp():  # Broadcast solution
                        print(f"Broadcaster: Broadcasting solution {event.solution}")
                        msg = SolutionFound(solution=event.solution)
                        await self._broadcast(msg, other_servers.values())
                    case _:
                        raise NotImplementedError(
                            f"Event {type(event)} is not recognized"
                        )
            await sleep(0.1)

    def log(self, msg: Any):
        print(f"{self.id}: {msg}")

    async def _broadcast(
        self, message: InterServerMessage, servers: Iterable[Optional[ServerHandle]]
    ):
        data = self.m.dumps(message).encode()
        for server in servers:
            if server is None:
                continue
            server.writer.write(data)

    def _is_solution(self): ...

    async def controller(self):
        self.log("Starting controller")
        # Bridges asyncio and processes
        while True:
            if not self.q2controller.empty():
                event = self.q2controller.get_nowait()
                match event:
                    case ToldSolutionOp():
                        self.log(f"Controller: Told solution recieved {event.solution}")
                        if self._is_solution():
                            self.blockchain.append(event.solution)
                            # Come up with new problem to solve
                            new_problem = randint(1, 64)
                            for p in self.miners.values():
                                p.q2m.put(OverrideProcessing(new_problem))
                    case _:
                        raise NotImplementedError(f"{type(event)} not supported.")
            await sleep(0.1)

            if not self.q2c.empty():
                event = self.q2c.get_nowait()
                match event:
                    case FoundSolutionOp():
                        self.log(f"Controller: Found Solution: {event.solution}")
                        await self.q2broadcaster.put(event)
                        self.blockchain.append(event.solution)
                        # Come up with new problem to solve
                        new_problem = randint(1, 64)
                        for miner_id, p in self.miners.items():
                            if event.miner_id == miner_id:
                                continue
                            p.q2m.put(OverrideProcessing(new_problem))
                    case _:
                        raise NotImplementedError(
                            f"Event {type(event)} is not recognized."
                        )
            await sleep(0.1)

            ...

    def srv(self):
        async def server(reader: StreamReader, writer: StreamWriter):
            # Server Program
            # - Listen for broadcasts
            # - Gossip protocol
            print("Starting Server")
            while True:
                msg = (await reader.readuntil(b"\n")).decode()
                msg = self.m.loads(msg)
                match msg:
                    case SolutionFound():
                        self.log(f"server: Solution Recieved: {msg.solution}")
                        await self.q2controller.put(
                            ToldSolutionOp(solution=msg.solution)
                        )
                    case Gossip():
                        for addr in msg.addresses:
                            self.other_servers[addr] = None
                        s = (
                            sample(list(self.other_servers.keys()), k=self.gossip_size)
                            if len(self.other_servers) >= self.gossip_size
                            else list(self.other_servers.keys())
                        )
                        writer.write(self.m.dumps(Gossip(addresses=s)).encode())
                    case _:
                        raise NotImplementedError(f"Found {type(msg)}")

        return server

    @staticmethod
    def miner(
        miner_id: str,
        q2m: MultiProcessQueue[MinerOp],
        q2c: MultiProcessQueue[ControllerOp],
    ):
        # Run program to compute nonce
        while True:
            if not q2m.empty():
                op = q2m.get_nowait()
                match op:
                    case OverrideProcessing():
                        print(
                            f"!{miner_id}: Overriding due to found solution. Now solving new problem '{op.new_problem}'"
                        )
                    case _:
                        raise NotImplementedError(f"Event {type(op)} not recognized")
            time.sleep(randint(1, 2))
            # found_solution = not bool(randint(0, 32))
            found_solution = bool(randint(0, 1))
            solution = randint(1, 32)
            if found_solution:
                print(f"!!!{miner_id}: Found Solution '{solution}'")
                q2c.put(FoundSolutionOp(miner_id, solution))
            else:
                print(f"{miner_id}: No solution")

    def append_block(self, block: Block):
        while val := block.try_compute_nonce():
            # Check other servers for a longer blockchain
            # Check for more known servers via gossip protocol
            ...


async def main():
    s1 = BlockchainServer([INetAddress("127.0.0.1", 8002)], 8001).run()
    s2 = BlockchainServer([INetAddress("127.0.0.1", 8001)], 8002).run()
    await gather(s1, s2)


if __name__ == "__main__":
    run(main())
