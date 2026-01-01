from multiprocessing import Process
from typing import Any
from .decorators import Handler, PeriodicHandlerAndData
from .event_driven import (
    Broadcaster,
    EventQueue,
    periodic_function,
)
from .service_config import ProcessGroup, ThreadGroup

MAPPINGS: dict[str, Handler] = {}


class Service:
    def __init__(self, config: dict[str, ThreadGroup | ProcessGroup]):
        self.event2queue: dict[object, EventQueue]
        self.event2list_queue: dict[object, list[EventQueue]]
        self.config = config

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
                                target = periodic_function
                                args = (
                                    process.name,
                                    process.dt,
                                    event_queue,
                                    broadcaster,
                                )
                            case _:
                                raise NotImplementedError(
                                    f"{type(process)} not implemented"
                                )

                        p = Process(
                            target=target,
                            args=(*args,),
                            daemon=True,
                        )
                        p.start()
                        p.join()
                        processes.append(p)
