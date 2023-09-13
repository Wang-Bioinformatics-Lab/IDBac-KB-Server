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
def task_deposit_data(deposit_dict, collection_name):
    print("Deposition", file=sys.stderr, flush=True)

    task = deposit_dict["task"]

    deposition_folder = os.path.join("database/depositions", "TASK-" + task)
    os.makedirs(deposition_folder, exist_ok=True)

    output_filename = os.path.join(deposition_folder, str(ULID()) + ".json")

    with open(output_filename, "w") as f:
        f.write(json.dumps(deposit_dict))

    return "Done"

@celery_instance.task(time_limit=600)
def task_summarize_depositions():
    print("Summarize", file=sys.stderr, flush=True)

    all_json_entries = glob.glob("database/depositions/**/*.json", recursive=True)
    
    spectra_list = []

    for json_filename in all_json_entries:
        print(json_filename, file=sys.stderr, flush=True)
        with open(json_filename, "r") as f:
            entry = json.loads(f.read())
            entry["database_id"] = os.path.basename(json_filename).replace(".json", "")

            # Drop all the peaks to save memory
            spectrum_obj.pop("spectrum", None)

            spectra_list.append(entry)

    # Summarizing
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