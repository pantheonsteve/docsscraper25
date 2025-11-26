# Datadog Logging Setup for DocsScraper

## ✅ What Was Fixed

### Issue 1: Logs Not Flowing to my-log.json
**Problem:** The `my_json` logger was defined but no code was using it.

**Solution:** Added the `json_file` handler to all active loggers (`django`, `crawler`, `dashboard`, `celery`) so all application logs now flow to `my-log.json` in JSON format.

### Issue 2: Datadog Agent Not Showing Logs
**Problem:** Datadog Agent wasn't configured to monitor your log files.

**Solution:** Created `/opt/datadog-agent/etc/conf.d/docsscraper.d/conf.yaml` to monitor:
- `/Users/steve.bresnick/Projects/docsscraper/logs/my-log.json`
- `/Users/steve.bresnick/Projects/docsscraper/logs/crawler.log`
- `/Users/steve.bresnick/Projects/docsscraper/logs/docanalyzer.log`

## ✅ Verification

### 1. Check Logs Are Being Written Locally
```bash
# View JSON logs
tail -f /Users/steve.bresnick/Projects/docsscraper/logs/my-log.json

# View crawler logs
tail -f /Users/steve.bresnick/Projects/docsscraper/logs/crawler.log
```

### 2. Check Datadog Agent Status
```bash
datadog-agent status | grep -A 30 "Logs Agent"
```

You should see:
- `LogsProcessed` and `LogsSent` counters increasing
- Your log files listed under "Integrations"
- Status: OK for each log file

### 3. Check Logs in Datadog UI
1. Go to https://app.datadoghq.com/logs
2. Filter by:
   - `service:docsscraper`
   - `env:dev`
   - `project:docsscraper`

## 📝 Current Configuration

### Django Loggers
All loggers now write to:
1. **Console** - for development visibility
2. **File** - human-readable logs in `logs/` directory
3. **JSON File** - structured logs in `logs/my-log.json` for Datadog

### Datadog Tags
- `env:dev` - Environment
- `project:docsscraper` - Project name
- `component:crawler` - For crawler-specific logs
- `component:analyzer` - For analyzer-specific logs

## 🔧 Troubleshooting

### If logs aren't appearing in Datadog:

1. **Check Agent is Running:**
   ```bash
   datadog-agent status
   ```

2. **Verify Log Files Exist:**
   ```bash
   ls -la /Users/steve.bresnick/Projects/docsscraper/logs/
   ```

3. **Generate Test Logs:**
   ```bash
   cd /Users/steve.bresnick/Projects/docsscraper
   source .venv/bin/activate
   python -c "
   import django, os, logging
   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
   django.setup()
   logger = logging.getLogger('crawler')
   logger.info('Test log message for Datadog')
   "
   ```

4. **Check File Permissions:**
   Ensure Datadog Agent can read your log files:
   ```bash
   chmod 644 /Users/steve.bresnick/Projects/docsscraper/logs/*.log
   chmod 644 /Users/steve.bresnick/Projects/docsscraper/logs/*.json
   ```

5. **Restart Datadog Agent:**
   The agent should auto-reload, but if needed:
   ```bash
   # Check current process
   ps aux | grep datadog-agent
   
   # On macOS, the agent typically runs as a service and auto-restarts
   ```

## 📊 Log Levels

Current log levels set to `INFO`. To change:

Edit `config/settings.py`:
```python
LOGGING['loggers']['crawler']['level'] = 'DEBUG'  # Or WARNING, ERROR
```

## 🎯 Expected Log Flow

1. Application logs → Python logger (e.g., `logger.info()`)
2. Django logging config → Multiple handlers:
   - Console handler → Terminal output
   - File handler → `logs/crawler.log`
   - JSON handler → `logs/my-log.json`
3. Datadog Agent → Tails log files
4. Datadog Agent → Sends to Datadog cloud
5. Datadog UI → Displays and indexes logs

## 📈 Monitoring Log Pipeline

Check if logs are flowing through the pipeline:

```bash
# Watch local JSON logs (source)
watch -n 1 'wc -l /Users/steve.bresnick/Projects/docsscraper/logs/my-log.json'

# Check Datadog agent stats
watch -n 5 'datadog-agent status | grep -E "LogsProcessed|LogsSent"'
```

## 🚀 Next Steps

1. Run your Django server: `ddtrace-run python manage.py runserver`
2. Navigate through the app to generate logs
3. Check Datadog UI in 1-2 minutes for logs to appear
4. Set up log monitors and alerts in Datadog UI

## 📚 Additional Resources

- [Datadog Python Logging](https://docs.datadoghq.com/logs/log_collection/python/)
- [Django Logging Configuration](https://docs.djangoproject.com/en/stable/topics/logging/)
- [Datadog Log Explorer](https://docs.datadoghq.com/logs/explorer/)




