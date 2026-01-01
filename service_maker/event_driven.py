import asyncio
from datetime import timedelta
from typing import (
    Iterable,
    NoReturn,
    Optional,
)

from blockchain_server import (
    INetAddress,
)


def periodic_function(
    func_name: str,
    dt: timedelta,
    event_queue: EventQueue,
    broadcaster: Broadcaster,
) -> None:
    from service_maker.service import MAPPINGS

    func: PeriodicHandler = MAPPINGS[func_name]  # type: ignore

    async def f() -> NoReturn:
        while True:
            await asyncio.sleep(dt.total_seconds())
            await func(event_queue, broadcaster)

    asyncio.run(f())


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


class EventQueue:
    def put(self, obj: object) -> bool: ...

    def broadcast(self, obj: object) -> bool: ...

    def get[T](self, obj: type[T]) -> T: ...

    def try_get[T](self, obj: type[T]) -> Optional[T]: ...

    def is_empty[T](self, obj: type[T]) -> T: ...
