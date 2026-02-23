# Fortune City Backend - Production Guide

This guide outlines the steps to deploy the Fortune City backend in a production environment.

## Prerequisites

- Docker and Docker Compose
- Domain name and SSL certificate (recommended)
- Cloudinary account for media storage
- PostgreSQL database (if not using Docker Compose)

## Environment Variables

Copy `.env.production.example` to `.env` and fill in the values:

```bash
cp .env.production.example .env
```

### Essential Variables:
- `DATABASE_URL`: Your production PostgreSQL URL.
- `SECRET_KEY`: A long, random string for JWT signing.
- `ALLOWED_ORIGINS`: Comma-separated list of your frontend domains.
- `ALLOWED_HOSTS`: Comma-separated list of your backend domains.
- `CLOUDINARY_*`: Your Cloudinary credentials.

## Deployment with Docker (Recommended)

The easiest way to deploy is using Docker Compose:

```bash
docker-compose up -d --build
```

This will start:
1.  **PostgreSQL** database.
2.  **FastAPI** backend with Uvicorn (multi-worker).

## Manual Deployment

If you prefer to run manually:

1.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run Migrations**:
    ```bash
    alembic upgrade head
    ```

3.  **Start the server**:
    ```bash
    python production_run.py
    ```

## Security Features Implemented

- **GZip Compression**: Reduces response size for better performance.
- **CORS Protection**: Only allows specified origins.
- **Trusted Host Middleware**: Prevents HTTP Host Header attacks.
- **Security Headers**: Includes HSTS, CSP, X-Frame-Options, and X-Content-Type-Options.
- **Global Error Handling**: Prevents internal server details from leaking in 500 errors.
- **Log Rotation**: Prevents log files from growing indefinitely.
- **Connection Pooling**: Optimized for high-traffic database access.

## Maintenance

### Logs
Logs are stored in `backend.log` and are rotated automatically (up to 5 backups of 10MB each).

### Migrations
Always run `alembic upgrade head` after updating the code to ensure the database schema is up to date.
