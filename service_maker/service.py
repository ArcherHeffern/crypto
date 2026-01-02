import asyncio
from datetime import timedelta
from multiprocessing import Process, Queue
from time import sleep
from typing import Callable, NoReturn
from .decorators import (
    EventHandlerAndData,
    Handler,
    PeriodicHandlerAndData,
)
from .event_driven import (
    Broadcaster,
    EventQueue,
)
from .service_config import ProcessGroup, ThreadGroup

MAPPINGS: dict[str, Handler] = {}


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


def event_handler_function(
    func_name: str,
    q: Queue,
    event_queue: EventQueue,
    broadcaster: Broadcaster,
):
    from service_maker.service import MAPPINGS

    func: EventHandler = MAPPINGS[func_name]  # type: ignore

    async def f() -> NoReturn:
        while True:
            try:
                v = q.get(timeout=0.2)
                await func(v, event_queue, broadcaster)
            except:
                ...
            sleep(0.1)

    asyncio.run(f())


def network_handler_function(config): ...


class Service:
    def __init__(
        self, config: dict[str, ThreadGroup | ProcessGroup], debug: bool = False
    ):
        self.config = config
        self.debug = debug

    def log(self, msg: str):
        if self.debug:
            print(msg)

    def run(self):
        # Create object of all types and what queues they map to
        # EventQueue will handle the routing by type and possibly duplicating the request if its a broadcast
        # Create processes for all queues

        # type -> handler_name -> queue
        group_data: dict[type, dict[str, Queue]] = {}
        master_queue = Queue()
        event_queue = EventQueue(group_data)
        broadcaster = Broadcaster()
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
                                    broadcaster,
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
                                    broadcaster,
                                )
                                processes_to_run.append((target, args))
                            case _:
                                raise NotImplementedError(
                                    f"{type(process)} not implemented"
                                )
        processes: list[Process] = []
        for target, args in processes_to_run:
            p = Process(
                target=target,
                args=(*args,),
                daemon=True,
            )
            p.start()
            processes.append(p)
            self.log(f"Started {args[0]}")

        for p in processes:
            p.join()
