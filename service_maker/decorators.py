from abc import ABC
from dataclasses import dataclass
from datetime import timedelta
from typing import Awaitable, Callable, Optional

from service_maker.event_driven import Broadcaster, EventQueue, Responder


@dataclass
class HandlerAndData(ABC):
    name: str


type RequestHandler[T] = Callable[
    [T, EventQueue, Broadcaster, Responder], Awaitable[None]
]


@dataclass
class RequestHandlerAndData[T](HandlerAndData):
    handler: RequestHandler[T]
    t: type[T]


def request_handler[T](
    name: str,
    msg_type: type[T],
) -> Callable[[RequestHandler[T]], RequestHandlerAndData]:
    def decorator(func: RequestHandler[T]) -> RequestHandlerAndData:
        from service_maker.service import MAPPINGS

        MAPPINGS[name] = func
        return RequestHandlerAndData(name, func, msg_type)

    return decorator


type PeriodicHandler = Callable[[EventQueue, Broadcaster], Awaitable[None]]


@dataclass
class PeriodicHandlerAndData(HandlerAndData):
    handler: PeriodicHandler
    dt: timedelta


def periodic(
    name: str, dt: timedelta
) -> Callable[[PeriodicHandler], PeriodicHandlerAndData]:

    def decorator(func: PeriodicHandler) -> PeriodicHandlerAndData:
        from service_maker.service import MAPPINGS

        MAPPINGS[name] = func
        return PeriodicHandlerAndData(name, func, dt)

    return decorator


type WorkerHandler[T] = Callable[
    [Optional[T], EventQueue, Broadcaster, dict], Awaitable[None]
]


@dataclass
class WorkerHandlerAndData[T](HandlerAndData):
    handler: WorkerHandler[T]
    t: Optional[type[T]]


def worker[T](name: str, listen_for: Optional[type[T]]):
    def decorator(func: WorkerHandler[T]) -> WorkerHandlerAndData[T]:
        from service_maker.service import MAPPINGS

        MAPPINGS[name] = func
        return WorkerHandlerAndData(name, func, listen_for)

    return decorator


type EventHandler[T] = Callable[[T, EventQueue, Broadcaster], Awaitable[None]]

type Handler[T] = RequestHandler | PeriodicHandler | WorkerHandler | EventHandler


@dataclass
class EventHandlerAndData[T](HandlerAndData):
    handler: EventHandler[T]
    t: type[T]


def event_handler[T](name: str, t: type[T]):
    def decorator(func: EventHandler[T]) -> EventHandlerAndData[T]:
        from service_maker.service import MAPPINGS

        MAPPINGS[name] = func
        return EventHandlerAndData(name, func, t)

    return decorator
