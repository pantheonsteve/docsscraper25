from django.core.management.base import BaseCommand
import subprocess
import sys
import os


class Command(BaseCommand):
    help = "Start Celery worker and (optionally) beat for local development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--beat",
            action="store_true",
            help="Also start celery beat alongside the worker.",
        )

    def handle(self, *args, **options):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        self.stdout.write(self.style.MIGRATE_HEADING("Starting Celery processes..."))
        self.stdout.write(f"Project root: {project_root}")

        env = os.environ.copy()
        # Ensure we use the same Python executable / venv that runs manage.py
        python_executable = sys.executable

        cmds = []

        # Celery worker (required)
        worker_cmd = [
            python_executable,
            "-m",
            "celery",
            "-A",
            "config",
            "worker",
            "-l",
            "info",
            "-Q",
            "celery,crawling,analysis",
        ]
        cmds.append(("worker", worker_cmd))

        # Optional beat
        if options.get("beat"):
            beat_cmd = [
                python_executable,
                "-m",
                "celery",
                "-A",
                "config",
                "beat",
                "-l",
                "info",
            ]
            cmds.append(("beat", beat_cmd))

        processes = []
        try:
            for name, cmd in cmds:
                self.stdout.write(self.style.HTTP_INFO(f"Starting Celery {name}: {' '.join(cmd)}"))
                p = subprocess.Popen(
                    cmd,
                    cwd=project_root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                processes.append((name, p))

            self.stdout.write(
                self.style.SUCCESS(
                    "Celery processes started. They will keep running until you stop this command (Ctrl+C) "
                    "or terminate the processes manually."
                )
            )

            # Block and stream minimal output so user sees it's alive
            while True:
                alive = any(p.poll() is None for _, p in processes)
                if not alive:
                    break
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Stopping Celery processes..."))
            for name, p in processes:
                if p.poll() is None:
                    p.terminate()
            self.stdout.write(self.style.SUCCESS("Celery processes terminated."))


