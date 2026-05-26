"""
Background Job Scheduler Service using APScheduler
Manages async task execution for deployments, metrics collection, and cleanup
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from typing import Callable, Dict, Any, Optional
from functions.base import get_db_session, engine
from models.automation import BackgroundTask, TaskStatus

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Centralized background job scheduler for k8s-orchestrator
    Uses APScheduler for task management and SQLAlchemy for persistence
    """

    def __init__(self):
        """Initialize scheduler with SQLAlchemy jobstore"""
        jobstores = {
            'default': SQLAlchemyJobStore(engine=engine)
        }

        executors = {
            'default': ThreadPoolExecutor(max_workers=10)
        }

        job_defaults = {
            'coalesce': False,  # Run all missed executions
            'max_instances': 3,  # Max concurrent instances of same job
            'misfire_grace_time': 300  # 5 minutes grace period for misfires
        }

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        # Add event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)

    def start(self):
        """Start the background scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler started successfully")

    def shutdown(self, wait=True):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("APScheduler shutdown")

    def schedule_task(
        self,
        task_name: str,
        task_func: Callable,
        task_type: str,
        cluster_id: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
        run_date: Optional[datetime] = None,
        cron_trigger: Optional[Dict[str, str]] = None
    ) -> BackgroundTask:
        """
        Schedule a background task for execution

        Args:
            task_name: Human-readable task name
            task_func: Callable function to execute
            task_type: Task category (deployment, metrics_collection, cleanup, retirement_scan)
            cluster_id: Optional cluster ID for cluster-specific tasks
            parameters: Task-specific parameters to pass to task_func
            run_date: Schedule for specific datetime (one-time execution)
            cron_trigger: Schedule with cron pattern (recurring execution)
                         Example: {'hour': '2', 'minute': '0'} for daily at 2 AM

        Returns:
            BackgroundTask: Database record tracking the task
        """
        db = get_db_session()
        try:
            # Create database record
            task = BackgroundTask(
                task_name=task_name,
                task_type=task_type,
                cluster_id=cluster_id,
                parameters=parameters or {},
                status=TaskStatus.QUEUED,
                scheduled_at=run_date or datetime.utcnow()
            )
            db.add(task)
            db.commit()
            db.refresh(task)

            # Wrap task function to update database status
            def wrapped_task_func():
                return self._execute_task(task.id, task_func, parameters or {})

            # Schedule with APScheduler
            if run_date:
                # One-time execution at specific datetime
                job = self.scheduler.add_job(
                    wrapped_task_func,
                    'date',
                    run_date=run_date,
                    id=f'task_{task.id}'
                )
            elif cron_trigger:
                # Recurring execution with cron pattern
                job = self.scheduler.add_job(
                    wrapped_task_func,
                    'cron',
                    **cron_trigger,
                    id=f'task_{task.id}'
                )
            else:
                # Immediate execution
                job = self.scheduler.add_job(
                    wrapped_task_func,
                    id=f'task_{task.id}'
                )

            # Update task with scheduler job ID
            task.scheduler_job_id = job.id
            db.commit()

            logger.info(f"Scheduled task: {task_name} (ID: {task.id}, Job: {job.id})")
            return task

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to schedule task {task_name}: {str(e)}")
            raise
        finally:
            db.close()

    def _execute_task(self, task_id: int, task_func: Callable, parameters: Dict[str, Any]):
        """
        Execute task and update database status

        Args:
            task_id: BackgroundTask ID
            task_func: Function to execute
            parameters: Parameters to pass to task_func
        """
        db = get_db_session()
        try:
            # Update status to running
            task = db.query(BackgroundTask).get(task_id)
            if not task:
                logger.error(f"Task {task_id} not found in database")
                return

            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            db.commit()

            logger.info(f"Executing task {task_id}: {task.task_name}")

            # Execute task function
            result = task_func(**parameters)

            # Update status to completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.result = result if isinstance(result, dict) else {'success': True}
            db.commit()

            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            # Update status to failed
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error_message = str(e)
            db.commit()

            logger.error(f"Task {task_id} failed: {str(e)}")
            raise

        finally:
            db.close()

    def cancel_task(self, task_id: int) -> bool:
        """
        Cancel a scheduled task

        Args:
            task_id: BackgroundTask ID

        Returns:
            bool: True if cancelled successfully
        """
        db = get_db_session()
        try:
            task = db.query(BackgroundTask).get(task_id)
            if not task:
                logger.warning(f"Task {task_id} not found")
                return False

            # Remove from scheduler
            if task.scheduler_job_id:
                try:
                    self.scheduler.remove_job(task.scheduler_job_id)
                except Exception as e:
                    logger.warning(f"Failed to remove job {task.scheduler_job_id}: {str(e)}")

            # Update status
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            db.commit()

            logger.info(f"Task {task_id} cancelled")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to cancel task {task_id}: {str(e)}")
            return False
        finally:
            db.close()

    def get_task_status(self, task_id: int) -> Optional[BackgroundTask]:
        """
        Get current status of a task

        Args:
            task_id: BackgroundTask ID

        Returns:
            BackgroundTask: Task object or None if not found
        """
        db = get_db_session()
        try:
            return db.query(BackgroundTask).get(task_id)
        finally:
            db.close()

    def _job_executed(self, event):
        """APScheduler event handler for successful job execution"""
        logger.debug(f"Job {event.job_id} executed successfully")

    def _job_error(self, event):
        """APScheduler event handler for job errors"""
        logger.error(f"Job {event.job_id} failed with exception: {event.exception}")


# Global scheduler instance (initialized in app.py)
scheduler_service = None


def get_scheduler() -> SchedulerService:
    """Get global scheduler instance"""
    global scheduler_service
    if scheduler_service is None:
        scheduler_service = SchedulerService()
    return scheduler_service
