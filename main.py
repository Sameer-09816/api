from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
import re
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel
from urllib.parse import urlparse
import os

# Configuration
class Settings(BaseModel):
    app_name: str = "Threads Downloader API"
    app_version: str = "1.1.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    timeout: float = float(os.getenv("TIMEOUT", "10.0"))
    allowed_origins: list = os.getenv("ALLOWED_ORIGINS", "*").split(",")

settings = Settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Constants
TIMEOUT = settings.timeout
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
THREADSTER_BASE_URL = "https://threadster.app/download/{thread_id}"
ID_PATTERN = re.compile(r"/post/([A-Za-z0-9_-]+)")

# Models
class ThreadResponse(BaseModel):
    ok: bool
    message: str
    avatar: str | None = None
    caption: str | None = None
    url: list[str] | None = None
    username: str | None = None

# Helper Functions
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(url, follow_redirects=True, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} for URL {url}")
        raise
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {str(e)}")
        raise

def extract_thread_id(url_or_id: str) -> str | None:
    if not url_or_id:
        return None
    
    if url_or_id.startswith(("http://", "https://")):
        match = ID_PATTERN.search(url_or_id)
        if match:
            return match.group(1)
        return None
    return url_or_id.strip()

# Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "message": "Internal server error"},
    )

# Routes
@app.get("/download", response_model=ThreadResponse)
async def download_thread(url_or_id: str):
    thread_id = extract_thread_id(url_or_id)
    if not thread_id:
        logger.warning(f"Invalid input received: {url_or_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Threads URL or ID format"
        )

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        try:
            content = await fetch_url(client, THREADSTER_BASE_URL.format(thread_id=thread_id))
            soup = BeautifulSoup(content, "html.parser")

            download_wrapper = soup.find("div", class_="download__wrapper")
            if not download_wrapper:
                logger.error(f"No download wrapper found for ID {thread_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Content not found"
                )

            download_items = download_wrapper.find_all("div", class_="download_item")
            if not download_items:
                logger.error(f"No download items found for ID {thread_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No downloadable content found"
                )

            first_item = download_items[0]
            avatar = first_item.find("div", class_="download__item__profile_pic").find("img")["src"]
            username = first_item.find("div", class_="download__item__profile_pic").find("span").text
            caption = first_item.find("div", class_="download__item__caption__text").text

            download_urls = [
                link["href"] for item in download_items
                if (link := item.find("a", class_="btn download__item__info__actions__button"))
            ]

            if not download_urls:
                logger.error(f"No download URLs found for ID {thread_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No download links available"
                )

            return {
                "ok": True,
                "message": "Content retrieved successfully",
                "avatar": avatar,
                "caption": caption,
                "url": download_urls,
                "username": username
            }

        except Exception as e:
            logger.error(f"Error processing request for {thread_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing your request"
            )

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.app_version}

def get_application() -> FastAPI:
    return app
