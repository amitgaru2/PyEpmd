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


async def forward(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while True:
            data = await reader.read(BUFFER_SIZE)
            if not data:
                break
            logger.info(
                "Forwarding %d bytes to %s",
                len(data),
                writer.get_extra_info("peername"),
            )
            writer.write(data)
            await writer.drain()
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
        forward(client_reader, server_writer), forward(server_reader, client_writer)
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
