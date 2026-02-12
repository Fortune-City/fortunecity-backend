import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    # In production, you typically want to listen on all interfaces
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    # Workers should be calculated based on CPU cores: (2 x num_cores) + 1
    # For a typical 2-core cloud instance, 5 workers is good.
    workers = int(os.getenv("WORKERS", 4))

    print(f"Starting production server on {host}:{port} with {workers} workers")
    
    uvicorn.run(
        "main:app", 
        host=host, 
        port=port, 
        workers=workers,
        log_level="info",
        proxy_headers=True, # Trust X-Forwarded-Proto, etc. from Nginx
        forwarded_allow_ips="*" # Trust all proxies (configure strictly if needed)
    )
