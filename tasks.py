from celery import Celery
import glob
import sys
import os
import json
from ulid import ULID
import pandas as pd
import requests
import requests_cache
import xmltodict
from utils import populate_taxonomies, generate_tree
from utils import calculate_checksum

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

@celery_instance.task(time_limit=10000)
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
            entry.pop("spectrum", None)

            spectra_list.append(entry)
    
    # clean up all entries by removing whitespace for each key
    new_spectra_list = []
    for entry in spectra_list:
        new_entry = {}
        for key in entry:
            
            new_key = key.rstrip().lstrip()
            if new_key != key:
                new_entry[new_key] = entry[key]
            else:
                new_entry[key] = entry[key]

        new_spectra_list.append(new_entry)

    spectra_list = new_spectra_list

    # Get the taxonomies from genbank, falling back to NCBI taxid
    spectra_list = populate_taxonomies(spectra_list)

    # Summarizing the spectra
    df = pd.DataFrame(spectra_list)

    # Saving the summary
    df.to_csv("database/summary.tsv", index=False, sep="\t")

    # Update taxonomic tree
    generate_tree(df[df['NCBI taxid'].notna()]['NCBI taxid'])

    # Calling the nextflow script
    task_summarize_nextflow.delay()

    # Calculate checksum for the database
    checksum = calculate_checksum("/app/workflows/idbac_summarize_database/nf_output/idbac_database.json")
    with open("/app/workflows/idbac_summarize_database/nf_output/idbac_database.json.sha256", "w") as f:
        f.write(checksum)

    return "Done"


@celery_instance.task(time_limit=20000)
def task_summarize_nextflow():
    # Trying to cleanup the work folder
    try:
        os.system("rm -rf /app/workflows/idbac_summarize_database/work")
    except:
        pass

    # Now we'll call the NextFlow Script

    cmd = "cd /app/workflows/idbac_summarize_database/ && \
    nextflow run /app/workflows/idbac_summarize_database/nf_workflow.nf \
    --input_database /app/database/depositions \
    -profile docker \
    -c /app/workflows/idbac_summarize_database/nextflow.config"

    print(cmd)

    os.system(cmd)


# celery_instance.conf.beat_schedule = {
#     "cleanup": {
#         "task": "tasks._task_cleanup",
#         "schedule": 3600
#     }
# }


celery_instance.conf.task_routes = {
    'tasks.task_computeheartbeat': {'queue': 'depositionworker'},
    'tasks.task_deposit_data': {'queue': 'depositionworker'},

    'tasks.task_summarize_depositions': {'queue': 'summaryworker'},
    'tasks.task_summarize_nextflow': {'queue': 'summaryworker'},
}