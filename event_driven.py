# Plumbing
from abc import ABC
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from multiprocessing import Process
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    Literal,
    NoReturn,
    Optional,
)

from main import (
    INetAddress,
)


class ThreadGroup:
    def __init__(self, *threads: Handler):
        self.threads = threads


class ProcessGroup:
    def __init__(self, *processes: Handler):
        self.processes = processes


def run_async_entry(fn: Callable[..., Coroutine[None, None, None]], *args: Any) -> None:
    asyncio.run(fn(*args))


# HANDLERS: dict[str, Handler] = {}


class Service:
    def __init__(self, config: dict[str, ThreadGroup | ProcessGroup]):
        self.event2queue: dict[object, EventQueue]
        self.event2list_queue: dict[object, list[EventQueue]]
        self.config = config

    @staticmethod
    async def _periodic_function(
        func: PeriodicHandler,
        dt: timedelta,
        event_queue: EventQueue,
        broadcaster: Broadcaster,
    ) -> NoReturn:
        while True:
            await asyncio.sleep(dt.total_seconds())
            await func(event_queue, broadcaster)
            ...

    def run(self):
        group_data: dict[str, Any] = {}
        event_queue = EventQueue()
        broadcaster = Broadcaster()
        processes = []
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
                                f = self._periodic_function(
                                    process.handler,
                                    process.dt,
                                    event_queue,
                                    broadcaster,
                                )
                            case _:
                                raise NotImplementedError(
                                    f"{type(process)} not implemented"
                                )

                        print("HERE")
                        p = Process(
                            target=run_async_entry,
                            args=(
                                self._periodic_function,
                                process.handler,
                                process.dt,
                                event_queue,
                                broadcaster,
                            ),
                            daemon=True,
                        )
                        print("HERE")
                        p.start()
                        print("HERE")
                        processes.append(p)
                        print("HERE")


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


# Implementation


@dataclass
class Handler(ABC): ...


type RequestHandler[T] = Callable[
    [T, EventQueue, Broadcaster, Responder], Awaitable[None]
]


@dataclass
class RequestHandlerAndData[T](Handler):
    handler: RequestHandler[T]
    t: type[T]


# Decorators


def request_handler[T](
    msg_type: type[T],
) -> Callable[[RequestHandler[T]], RequestHandlerAndData]:
    def decorator(func: RequestHandler[T]) -> RequestHandlerAndData:
        return RequestHandlerAndData(func, msg_type)

    return decorator


type PeriodicHandler = Callable[[EventQueue, Broadcaster], Awaitable[None]]


@dataclass
class PeriodicHandlerAndData(Handler):
    handler: PeriodicHandler
    dt: timedelta


def periodic(dt: timedelta) -> Callable[[PeriodicHandler], PeriodicHandlerAndData]:
    def decorator(func: PeriodicHandler) -> PeriodicHandlerAndData:
        return PeriodicHandlerAndData(func, dt)

    return decorator


type WorkerHandler[T] = Callable[
    [Optional[T], EventQueue, Broadcaster, dict], Awaitable[None]
]


@dataclass
class WorkerHandlerAndData[T](Handler):
    handler: WorkerHandler[T]
    t: Optional[type[T]]


def worker[T](listen_for: Optional[type[T]]):
    def decorator(func: WorkerHandler[T]) -> WorkerHandlerAndData[T]:
        return WorkerHandlerAndData(func, listen_for)

    return decorator


type EventHandler[T] = Callable[[T, EventQueue, Broadcaster], Awaitable[None]]


@dataclass
class EventHandlerAndData[T](Handler):
    handler: EventHandler[T]
    t: type[T]


def event_handler[T](t: type[T]):
    def decorator(func: EventHandler[T]) -> EventHandlerAndData[T]:
        return EventHandlerAndData(func, t)

    return decorator


@periodic(timedelta(seconds=1))
async def hello_world_handler(
    event_queue: EventQueue, broadcaster: Broadcaster
) -> None:
    print("Hello world")


if __name__ == "__main__":
    p = Service(config={"hello_world": ProcessGroup(hello_world_handler)})
    p.run()
