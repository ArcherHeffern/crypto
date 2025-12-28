from asyncio import create_task, open_connection, start_server
from unittest import TestCase, main

from main import BlockchainServer, INetAddress


class Tests(TestCase):
    async def test_broadcaster(self):
        # other_server_address = INetAddress("127.0.0.1", 8001)
        # s = BlockchainServer([other_server_address], 1)
        # print("a")
        # r, w = await start_server()
        # t = create_task(s.broadcaster())
        # t.cancel()
        ...


if __name__ == "__main__":
    main()
