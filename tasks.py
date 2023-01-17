from celery import Celery
import glob
import sys
import os
import json
from ulid import ULID
import pandas as pd

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

    all_json_entries = glob.glob("database/depositions/*.json")
    
    spectra_list = []

    for json_filename in all_json_entries:
        with open(json_filename, "r") as f:
            entry = json.loads(f.read())
            entry["database_id"] = os.path.basename(json_filename).replace(".json", "")
            spectra_list.append(entry)

    # Summarizing
    for spectrum_obj in spectra_list:
        spectrum_obj.pop("peaks", None)

    df = pd.DataFrame(spectra_list)

    # Saving the summary
    df.to_csv("database/summary.tsv", index=False, sep="\t")

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
    'tasks.task_summarize_depositions': {'queue': 'worker'},
}