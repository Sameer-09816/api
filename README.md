# Threads Downloader API

A FastAPI service for downloading Threads content.

## Deployment

1. Clone the repository
2. Build Docker image: `docker build -t threads-downloader .`
3. Run container: `docker run -p 8080:8080 threads-downloader`

## Environment Variables

- `DEBUG`: Enable debug mode (default: false)
- `TIMEOUT`: Request timeout in seconds (default: 10.0)
- `ALLOWED_ORIGINS`: Comma-separated list of allowed origins (default: *)

## Endpoints

- `GET /download?url_or_id=<threads_url_or_id>`: Download Threads content
- `GET /health`: Health check endpoint
