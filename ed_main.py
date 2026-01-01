from datetime import timedelta
from service_maker import Service, ProcessGroup
from service_maker.decorators import periodic
from service_maker.event_driven import Broadcaster, EventQueue


@periodic("hello_world_handler", timedelta(seconds=1))
async def hello_world_handler(
    event_queue: EventQueue, broadcaster: Broadcaster
) -> None:
    print("Hello world")


def main() -> None:
    s = Service(config={"hello_world": ProcessGroup(hello_world_handler)})
    s.run()


if __name__ == "__main__":
    main()
