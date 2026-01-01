from dataclasses import dataclass
from datetime import timedelta
from service_maker import (
    Service,
    ProcessGroup,
    event_handler,
    periodic,
    Broadcaster,
    EventQueue,
)


@dataclass
class Frog:
    name: str
    say: str


@periodic("frog_periodic", timedelta(seconds=1))
async def frog_periodic(event_queue: EventQueue, broadcaster: Broadcaster) -> None:
    frog = Frog("froggie", "ribbit")
    print("Sending Frog")
    event_queue.put(frog)


@event_handler("frog_handler", Frog)
async def frog_handler(frog: Frog, event_queue: EventQueue, broadcaster: Broadcaster):
    print(f"Frog '{frog.name}' says {frog.say}")


def main() -> None:
    s = Service(
        config={"hello_world": ProcessGroup(frog_periodic, frog_handler)}, debug=True
    )
    s.run()


if __name__ == "__main__":
    main()
