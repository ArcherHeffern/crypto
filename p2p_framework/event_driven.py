from abc import ABC
from dataclasses import dataclass
from multiprocessing import Queue
from random import choice

from blockchain_server import (
    INetAddress,
)


@dataclass
class MsgTo(ABC): ...


type PeerId = int


@dataclass(frozen=True)
class PeerConnected:
    peer_id: PeerId
    address: INetAddress
    inbound: bool


@dataclass(frozen=True)
class PeerDisconnected:
    peer_id: PeerId
    address: INetAddress
    reason: str


# API


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

    def broadcast(self, obj: MsgTo) -> bool:
        """
        Broadcasts obj to all event handlers for type(obj)
        """
        t: type = type(obj)
        qs = self.group_data[t]
        for q in qs.values():
            q.put_nowait(obj)
        return True
