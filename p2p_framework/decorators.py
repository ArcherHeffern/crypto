from abc import ABC
from dataclasses import dataclass
from datetime import timedelta
from multiprocessing import Queue
from typing import Awaitable, Callable, Iterable, Optional

from blockchain_server import INetAddress
from p2p_framework.event_driven import (
    EventQueue,
    MsgTo,
    PeerConnected,
    PeerDisconnected,
    PeerId,
)


@dataclass
class HandlerAndData(ABC):
    name: str


@dataclass
class MsgFrom[T: MsgTo](ABC):
    peer_id: PeerId
    msg: T


type RequestHandler[T: MsgTo] = Callable[
    [MsgFrom[T], EventQueue, Networker], Awaitable[None]
]


@dataclass
class RequestHandlerAndData[T: MsgTo](HandlerAndData):
    handler: RequestHandler[T]
    t: type[T]


def request_handler[T: MsgTo](
    name: str,
    msg_type: type[T],
) -> Callable[[RequestHandler[T]], RequestHandlerAndData]:
    def decorator(func: RequestHandler[T]) -> RequestHandlerAndData:
        from p2p_framework.service import MAPPINGS

        MAPPINGS[name] = func
        return RequestHandlerAndData(name, func, msg_type)

    return decorator


type PeriodicHandler = Callable[[EventQueue, Networker], Awaitable[None]]


@dataclass
class PeriodicHandlerAndData(HandlerAndData):
    handler: PeriodicHandler
    dt: timedelta


def periodic(
    name: str, dt: timedelta
) -> Callable[[PeriodicHandler], PeriodicHandlerAndData]:

    def decorator(func: PeriodicHandler) -> PeriodicHandlerAndData:
        from p2p_framework.service import MAPPINGS

        MAPPINGS[name] = func
        return PeriodicHandlerAndData(name, func, dt)

    return decorator


type WorkerHandler[T] = Callable[
    [Optional[T], EventQueue, Networker, dict], Awaitable[None]
]


@dataclass
class WorkerHandlerAndData[T](HandlerAndData):
    handler: WorkerHandler[T]
    t: Optional[type[T]]


def worker[T](name: str, listen_for: Optional[type[T]]):
    def decorator(func: WorkerHandler[T]) -> WorkerHandlerAndData[T]:
        from p2p_framework.service import MAPPINGS

        MAPPINGS[name] = func
        return WorkerHandlerAndData(name, func, listen_for)

    return decorator


type EventHandler[T] = Callable[[T, EventQueue, Networker], Awaitable[None]]

type Handler[T] = RequestHandler | PeriodicHandler | WorkerHandler | EventHandler


@dataclass
class EventHandlerAndData[T: MsgTo | PeerConnected | PeerDisconnected](HandlerAndData):
    handler: EventHandler[T]
    t: type[T]


def event_handler[T: MsgTo | PeerConnected | PeerDisconnected](name: str, t: type[T]):
    def decorator(func: EventHandler[T]) -> EventHandlerAndData[T]:
        from p2p_framework.service import MAPPINGS

        MAPPINGS[name] = func
        return EventHandlerAndData(name, func, t)

    return decorator


@dataclass
class NetworkEvent: ...


@dataclass
class Connect(NetworkEvent):
    address: INetAddress


@dataclass
class Disconnect(NetworkEvent):
    peer_id: PeerId


@dataclass
class Broadcast(NetworkEvent):
    msg: MsgTo
    exclude_peer_ids: Optional[list[PeerId]] = None


@dataclass
class Send(NetworkEvent):
    peer_id: PeerId
    msg: MsgTo


@dataclass
class Networker:
    q: Queue[NetworkEvent]

    def connect(self, address: INetAddress) -> Optional[PeerId]:
        self.q.put_nowait(Connect(address))

    def disconnect(self, address: PeerId):
        self.q.put_nowait(Disconnect(address))

    def broadcast(self, msg: MsgTo, exclude_peer_ids: Optional[list[PeerId]] = None):
        self.q.put_nowait(Broadcast(msg, exclude_peer_ids))

    def send(self, address: PeerId, msg: MsgTo):
        self.q.put_nowait(Send(address, msg))

    def get_peer_ids(self) -> Iterable[PeerId]:
        raise NotImplementedError("get_peer_ids is not implemented")

    def get_addresses(self) -> Iterable[INetAddress]:
        raise NotImplementedError("get_addresses is not implemented")
