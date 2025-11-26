"""
API views for crawler functionality.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from core.models import CrawlJob
import json
import logging
from ddtrace import tracer

logger = logging.getLogger('crawler')

@tracer.wrap()
@require_http_methods(["GET"])
def crawl_status(request, job_id):
    """
    Get the status of a crawl job.
    """
    try:
        job = CrawlJob.objects.get(id=job_id)
        logger.info(f"Crawl status for job {job_id}: {job.status}")
        return JsonResponse({
            'id': job.id,
            'status': job.status,
            'target_url': job.target_url,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'duration': job.get_duration(),
            'stats': job.stats,
            'progress_percentage': job.progress_percentage,
            'pages_per_second': job.get_pages_per_second(),
            'error_message': job.error_message,
        })
    except CrawlJob.DoesNotExist:
        logger.error(f"Job {job_id} not found")
        return JsonResponse({'error': 'Job not found'}, status=404)


@tracer.wrap()
@csrf_exempt
@require_http_methods(["POST"])
def start_crawl(request):
    """
    Start a new crawl job.
    """
    logger.info(f"Starting crawl for client {client_id} and target URL {target_url}")
    try:
        data = json.loads(request.body)
        client_id = data.get('client_id')
        target_url = data.get('target_url')
        config = data.get('config', {})

        if not client_id or not target_url:
            return JsonResponse({
                'error': 'client_id and target_url are required'
            }, status=400)

        # Create the job
        from core.models import Client
        client = Client.objects.get(id=client_id)
        job = CrawlJob.objects.create(
            client=client,
            target_url=target_url,
            config=config
        )

        # Start the crawl task
        from .tasks import start_crawl_task
        task = start_crawl_task.delay(job.id)
        job.celery_task_id = task.id
        job.save(update_fields=['celery_task_id'])

        return JsonResponse({
            'job_id': job.id,
            'status': job.status,
            'celery_task_id': task.id
        }, status=201)

    except Client.DoesNotExist:
        logger.error(f"Client {client_id} not found")
        return JsonResponse({'error': 'Client not found'}, status=404)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON for client {client_id}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error starting crawl for client {client_id}: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
