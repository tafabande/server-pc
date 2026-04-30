import uvicorn
from config import HOST, PORT
from core.utils import _kill_process_on_port

if __name__ == "__main__":
    # Kill any existing process on the port before starting to avoid address binding errors
    _kill_process_on_port(PORT)
    
    # Now Uvicorn imports core.main for the first and ONLY time,
    # preventing Prometheus Gauge namespace collisions.
    uvicorn.run(
        "core.main:app", 
        host=HOST, 
        port=PORT, 
        log_level="info",
        access_log=True
    )
