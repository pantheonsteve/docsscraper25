# Setup Guide

This guide will walk you through setting up the DocAnalyzer system from scratch.

## System Requirements

- macOS, Linux, or Windows with WSL2
- Python 3.11 or higher
- Podman Desktop (with podman-compose)
- 4GB RAM minimum (8GB recommended)
- 10GB free disk space

## Step-by-Step Setup

### 1. Install Prerequisites

#### Python 3.11+
```bash
# macOS (using Homebrew)
brew install python@3.11

# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Check version
python3 --version
```

#### Podman Desktop
Download and install from: https://podman-desktop.io/

Verify tools:
```bash
podman --version
podman-compose --version
```

#### Git
```bash
# macOS
brew install git

# Ubuntu/Debian
sudo apt install git
```

### 2. Clone and Setup Project

```bash
# Navigate to your projects directory
cd ~/Projects

# If not already there, clone or initialize
cd docsscraper

# Verify files are present
ls -la
```

### 3. Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate

# Verify activation (should show venv path)
which python
```

### 4. Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt

# This will install:
# - Django and related packages
# - Scrapy and crawling tools
# - Celery for task processing
# - PostgreSQL driver
# - Redis client
# - and more...
```

### 5. Install Playwright Browsers

```bash
# Install Chromium browser for JavaScript rendering
playwright install chromium

# This downloads ~150MB
```

### 6. Start Containers with Podman

```bash
# Start PostgreSQL and Redis in background
podman-compose up -d

# Verify containers are running
podman-compose ps

# You should see:
# - docanalyzer_postgres (port 5432)
# - docanalyzer_redis (port 6379)

# Check logs if needed
podman-compose logs postgres
podman-compose logs redis
```

### 7. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your settings
# On macOS:
nano .env

# Minimum required settings:
# SECRET_KEY=your-secret-key-here
# DEBUG=True
# (Database and Redis settings are already configured for local development)
```

### 8. Initialize Database

```bash
# Create database tables
python manage.py migrate

# You should see output like:
# Running migrations:
#   Applying contenttypes.0001_initial... OK
#   Applying auth.0001_initial... OK
#   ...
```

### 9. Create Admin User

```bash
# Create superuser for Django admin
python manage.py createsuperuser

# Enter:
# - Username: admin (or your choice)
# - Email: your@email.com
# - Password: (enter twice)
```

### 10. Verify Installation

```bash
# Start Django development server
python manage.py runserver

# You should see:
# Starting development server at http://127.0.0.1:8000/
# Quit the server with CONTROL-C.

# Open browser to:
# - Dashboard: http://localhost:8000/
# - Admin: http://localhost:8000/admin/
```

### 11. Start Celery Worker

Open a **new terminal window/tab**:

```bash
# Navigate to project
cd ~/Projects/docsscraper

# Activate virtual environment
source venv/bin/activate

# Start Celery worker
celery -A config worker -l info -Q crawling,analysis

# You should see:
# celery@hostname ready.
```

### 12. Test a Crawl

Open **another terminal window/tab**:

```bash
# Navigate to project
cd ~/Projects/docsscraper

# Activate virtual environment
source venv/bin/activate

# Run a test crawl (use a small documentation site)
python manage.py crawl \
  --url=https://docs.python.org/3/library/os.html \
  --depth=1 \
  --async

# You should see:
# Created crawl job #1 for https://docs.python.org/3/library/os.html
# Crawl started asynchronously (Celery task: ...)
# Monitor progress with: python manage.py crawl_status --job=1
```

### 13. Monitor the Crawl

```bash
# Check crawl status
python manage.py crawl_status --job=1

# View in dashboard
# Open browser: http://localhost:8000/
# Click on job #1 to see details
```

## Verification Checklist

- [ ] Containers running via podman-compose (postgres, redis)
- [ ] Python virtual environment activated
- [ ] Django server running on port 8000
- [ ] Celery worker running and ready
- [ ] Admin interface accessible
- [ ] Test crawl completed successfully

## Common Issues and Solutions

### Issue: Containers won't start (Podman)

**Solution:**
```bash
# Stop containers
podman-compose down

# Remove volumes and restart
podman-compose down -v
podman-compose up -d

# Check logs
podman-compose logs
```

### Issue: Database connection errors

**Solution:**
```bash
# Check PostgreSQL container
podman-compose ps postgres

# Verify database exists
podman-compose exec postgres psql -U docanalyzer -d docanalyzer -c "\dt"

# If needed, recreate database
podman-compose down -v
podman-compose up -d
python manage.py migrate
```

### Issue: Celery worker not starting

**Solution:**
```bash
# Check Redis is accessible
podman-compose ps redis

# Try connecting to Redis
podman-compose exec redis redis-cli ping
# Should return: PONG

# Check Celery configuration
python manage.py shell
>>> from config import celery
>>> celery.app
```

### Issue: ImportError or ModuleNotFoundError

**Solution:**
```bash
# Verify virtual environment is activated
which python  # Should show path to venv

# Reinstall requirements
pip install -r requirements.txt

# Check Django installation
python -c "import django; print(django.get_version())"
```

### Issue: Port already in use

**Solution:**
```bash
# If port 8000 is in use
python manage.py runserver 8001

# If port 5432 (postgres) is in use
# Edit docker-compose.yml to use different port:
# ports:
#   - "5433:5432"
# Then update .env DB_PORT=5433
```

### Issue: Permission denied (logs directory)

**Solution:**
```bash
# Create logs directory
mkdir -p logs

# Set permissions
chmod 755 logs
```

## Next Steps

1. **Explore the Admin Interface**
   - Create a client: http://localhost:8000/admin/core/client/
   - View crawled pages: http://localhost:8000/admin/crawler/crawledpage/

2. **Run More Crawls**
   - Try different documentation sites
   - Experiment with depth limits
   - Test domain filtering

3. **Customize Configuration**
   - Adjust crawler politeness settings
   - Configure custom user agent
   - Set up webhook notifications

4. **Review Architecture**
   - Read CLAUDE.md for architecture details
   - Explore the codebase structure
   - Review data models

## Development Workflow

Your typical development session:

```bash
# Terminal 1: Start infrastructure
podman-compose up -d

# Terminal 2: Start Django
source venv/bin/activate
python manage.py runserver

# Terminal 3: Start Celery
source venv/bin/activate
celery -A config worker -l info -Q crawling,analysis

# Terminal 4: Run commands
source venv/bin/activate
python manage.py crawl --url=...
```

## Shutting Down

```bash
# Stop Django server: Ctrl+C in Terminal 2
# Stop Celery worker: Ctrl+C in Terminal 3

# Stop containers
podman-compose stop

# Or completely remove containers
podman-compose down
```

## Getting Help

If you encounter issues not covered here:

1. Check the logs:
   - Django: Terminal output
   - Celery: Terminal output
   - Crawler: `logs/crawler.log`
   - General: `logs/docanalyzer.log`

2. Check container logs:
   ```bash
   podman-compose logs postgres
   podman-compose logs redis
   ```

3. Verify all services:
   ```bash
   # Django
   curl http://localhost:8000/

   # PostgreSQL
   podman-compose exec postgres pg_isready

   # Redis
   podman-compose exec redis redis-cli ping
   ```
