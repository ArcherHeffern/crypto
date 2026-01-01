import asyncio
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


# API


class Broadcaster:
    def connect(self, address: INetAddress): ...

    def disconnect(self, address: INetAddress): ...

    def broadcast(self, obj: object): ...

    def send(self, address: INetAddress, obj: object): ...

    def get_connections(self) -> Iterable[INetAddress]: ...

    def add_connection(self, address: INetAddress) -> bool: ...

    def add_connections(self, addresses: Iterable[INetAddress]) -> bool: ...


class Responder:
    def respond(self, msg: object) -> bool: ...


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
