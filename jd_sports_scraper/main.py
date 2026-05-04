import asyncio
import sys
from src.scraper import main

if __name__ == "__main__":
    handles = sys.argv[1:] or None
    asyncio.run(main(handles))
