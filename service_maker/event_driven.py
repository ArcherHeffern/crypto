from asyncio import StreamReader, StreamWriter, open_connection
from dataclasses import dataclass
from datetime import timedelta
from multiprocessing import Queue
from random import choice
from time import sleep
from typing import (
    Callable,
    Iterable,
    NoReturn,
    Optional,
)

from blockchain_server import (
    INetAddress,
)
from service_maker.decorators import PeerId, MsgTo


@dataclass(frozen=True)
class PeerConnected:
    peer_id: str
    address: INetAddress
    inbound: bool


@dataclass(frozen=True)
class PeerDisconnected:
    peer_id: str
    address: INetAddress
    reason: str


# API


@dataclass
class Broadcaster:
    def connect(self, address: INetAddress) -> Optional[PeerId]: ...

    def disconnect(self, address: PeerId): ...

    def broadcast(self, obj: MsgTo): ...

    def send(self, address: PeerId, obj: MsgTo): ...

    def get_peer_ids(self) -> Iterable[PeerId]: ...

    def get_addresses(self) -> Iterable[INetAddress]: ...


class Responder:
    def respond(self, msg: MsgTo) -> bool: ...


@dataclass
class EventQueue:
    group_data: dict[type, dict[str, Queue]]

    def put(self, obj: object) -> bool:
        """
        Sends obj to a random event handler for type(obj)
        """
        t: type = type(obj)
        qs = self.group_data[t]
        random_q = choice(list(qs.values()))
        random_q.put_nowait(obj)
        return True

    def broadcast(self, obj: object) -> bool:
        """
        Broadcasts obj to all event handlers for type(obj)
        """
        t: type = type(obj)
        qs = self.group_data[t]
        for q in qs.values():
            q.put_nowait(obj)
        return True
