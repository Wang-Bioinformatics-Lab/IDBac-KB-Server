from celery import Celery
import glob
import sys
import os
from ulid import ULID

celery_instance = Celery('tasks', backend='redis://idbac-kb-redis', broker='pyamqp://guest@idbac-kb-rabbitmq//', )

@celery_instance.task(time_limit=60)
def task_computeheartbeat():
    print("UP", file=sys.stderr, flush=True)
    return "Up"


@celery_instance.task(time_limit=60)
def task_deposit_data(deposit_dict):
    print("Deposition", file=sys.stderr, flush=True)

    output_filename = os.path.join("database/depositions", str(ULID()) + ".json")

    with open(output_filename, "w") as f:
        f.write(json.dumps(deposit_dict))

    return "Done"

@celery_instance.task(time_limit=60)
def task_summarize_depositions():
    print("Summarize", file=sys.stderr, flush=True)

    raise Exception("Not Implemented")

    return "Done"

# celery_instance.conf.beat_schedule = {
#     "cleanup": {
#         "task": "tasks._task_cleanup",
#         "schedule": 3600
#     }
# }


celery_instance.conf.task_routes = {
    'tasks.task_computeheartbeat': {'queue': 'worker'},
    'tasks.task_deposit_data': {'queue': 'worker'},
}