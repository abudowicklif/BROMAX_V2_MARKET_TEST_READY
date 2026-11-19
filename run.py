import uvicorn
from bromax.config import settings

if __name__ == "__main__":
    uvicorn.run("bromax.main:app", host=settings.host, port=settings.port, reload=False)
