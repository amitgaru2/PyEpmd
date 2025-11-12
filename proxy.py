import time
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    filename="tcp_proxy.log",
    filemode="a",
)

logger = logging.getLogger()


LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8000

FORWARD_HOST = "127.0.0.1"
FORWARD_PORT = 6000

BUFFER_SIZE = 4096


class TimedPacketQueue:
    delay = 0.5  # seconds

    def __init__(self):
        self.queue = []

    def push(self, item, writer):
        self.queue.append((item, writer, time.time()))

    def pop(self):
        if self.queue and self.queue[0][2] + self.delay <= time.time():
            return self.queue.pop(0)[0:2]
        else:
            return None, None

    def empty(self):
        return len(self.queue) == 0


packet_queue = TimedPacketQueue()


async def periodic_packet_processor():
    while True:
        await asyncio.sleep(0.1)
        data, writer = packet_queue.pop()
        if data is not None:
            try:
                logger.info("Processing delayed packet of size %d", len(data))
                writer.write(data)
                await writer.drain()
            except Exception as e:
                logger.error("Error processing delayed packet: %s", e)


async def forward(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while True:
            data = await reader.read(BUFFER_SIZE)
            if not data:
                break
            logger.info(
                "Queuing %d bytes.",
                len(data),
                # writer.get_extra_info("peername"),
            )
            packet_queue.push(data, writer)
            # writer.write(data)
            # await writer.drain()
    except Exception as e:
        logger.error("Error during forwarding: %s", e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logger.error("Error closing writer: %s", e)
            pass


async def handle_client(client_reader, client_writer):
    try:
        server_reader, server_writer = await asyncio.open_connection(
            FORWARD_HOST, FORWARD_PORT
        )
    except Exception as e:
        logger.error("Failed to connect to target: %s", e)
        client_writer.close()
        await client_writer.wait_closed()
        return

    # Forward data both ways concurrently
    await asyncio.gather(
        forward(client_reader, server_writer),
        forward(server_reader, client_writer),
        periodic_packet_processor(),
    )


async def main():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    # addr = server.sockets[0].getsockname()
    # logger.info(f"Serving on {addr}")
    logger.info(
        f"Forwarding {LISTEN_HOST}:{LISTEN_PORT} -> {FORWARD_HOST}:{FORWARD_PORT}"
    )

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Proxy stopped.")
