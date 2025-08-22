from src.server import server
from uvicorn import run

if __name__ == "__main__":
    run(server, host="0.0.0.0", port=8841)