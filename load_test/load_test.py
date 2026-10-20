
import argparse
import asyncio
import time
from collections import Counter

import httpx


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/api/products"
    )
    parser.add_argument("--rps", type=float, default=20)
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--clients", type=int, default=10)
    args = parser.parse_args()

    if args.rps <= 0 or args.duration <= 0 or args.clients <= 0:
        parser.error("--rps, --duration and --clients must be positive")

    counter = Counter()
    semaphore = asyncio.Semaphore(args.clients)
    interval = 1 / args.rps
    end_time = time.monotonic() + args.duration

    async with httpx.AsyncClient(timeout=10.0) as client:

        async def send_request():
            async with semaphore:
                try:
                    response = await client.get(args.url)
                    counter[response.status_code] += 1

                except httpx.TimeoutException as exc:
                    counter["timeout"] += 1
                    print(f"TIMEOUT: {type(exc).__name__}: {exc}")

                except httpx.RequestError as exc:
                    counter["request_error"] += 1
                    print(f"REQUEST ERROR: {type(exc).__name__}: {exc}")

                except Exception as exc:
                    counter["other_error"] += 1
                    print(f"OTHER ERROR: {type(exc).__name__}: {exc}")

        tasks = []
        start_time = time.monotonic()
        next_request = start_time

        while next_request < end_time:
            tasks.append(asyncio.create_task(send_request()))
            next_request += interval

            delay = next_request - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)

        await asyncio.gather(*tasks)

    print("\n--- Load Test Results ---")
    print(f"URL: {args.url}")
    print(f"Target RPS: {args.rps}")
    print(f"Duration: {args.duration}s")
    print(f"Requests completed: {sum(counter.values())}")
    print(f"Response/error counts: {dict(counter)}")


if __name__ == "__main__":
    asyncio.run(main())
