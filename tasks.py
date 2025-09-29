from celery import Celery
import glob
import sys
import os
import json
import traceback
from ulid import ULID
import pandas as pd
import re
import requests
import requests_cache
import xmltodict
from utils import populate_taxonomies, generate_tree
from utils import calculate_checksum
from time import time

dev_mode = False
if not os.path.isdir('/app'):
    dev_mode =  True

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

@celery_instance.task(time_limit=60*60*23) # 23 Hours
def task_summarize_depositions():
    print("Summarize", file=sys.stderr, flush=True)

    all_json_entries = glob.glob("database/depositions/**/*.json", recursive=True)
    
    spectra_list = []

    for json_filename in all_json_entries:
        print(json_filename, file=sys.stderr, flush=True)
        with open(json_filename, "r") as f:
            entry = json.loads(f.read())
            entry["database_id"] = os.path.basename(json_filename).replace(".json", "")
            # Clean 'NCBI taxid' to be int or None using regex
            try:
                txid = entry.get("NCBI taxid", None)
                if txid is not None:
                    # Extract digits using regex
                    match = re.search(r'\d+', str(txid))
                    if match:
                        entry["NCBI taxid"] = int(match.group(0))

            except Exception:
                print(f"Error parsing NCBI taxid {txid}", file=sys.stderr, flush=True)
                # Print full exception (without stacktrace)
                print(traceback.format_exc(), file=sys.stderr, flush=True)

            # Clean the 'Genabnk accession' to take whatever is after a space, colon, or pipe
            try:
                gb_acc = entry.get("Genbank accession", None)
                if gb_acc is not None:
                    # Split by space, colon, or pipe and take the last part
                    parts = re.split(r'[ :|]', gb_acc)
                    entry["Genbank accession"] = parts[-1].strip()
            except Exception:
                print(f"Error parsing Genbank accession {gb_acc}", file=sys.stderr, flush=True)
                # Print full exception (without stacktrace)
                print(traceback.format_exc(), file=sys.stderr, flush=True)

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
    start_time = time()
    print("Populating taxonomies", file=sys.stderr, flush=True)
    spectra_list = populate_taxonomies(spectra_list)
    print(f"Populating taxonomies took {(time() - start_time)/60:.2f} minutes", file=sys.stderr, flush=True)

    # Check that we successfully populated any taxonomy, if not, there was likely an error
    populated_some_species = False
    for entry in spectra_list:
        _species = entry.get("species")
        if _species is not None and len(_species) > 0:
            populated_some_species = True
            break

    if not populated_some_species:
        print("No species populated, requeuing task", file=sys.stderr, flush=True)
        task_summarize_depositions.apply_async(countdown=2*60*60)   # Retry in 2 hours
        return "No species populated, requeuing task"

    # Save the spectra list to a file
    print("Writing to json", file=sys.stderr, flush=True)
    with open("database/summary.json", "w") as f:
        f.write(json.dumps(spectra_list))

    # Summarizing the spectra
    print("Writing to tsv", file=sys.stderr, flush=True)
    df = pd.DataFrame(spectra_list)

    # Saving the summary
    df.to_csv("database/summary.tsv", index=False, sep="\t")

    # Save summary statistics
    summary_statistics = {
        "num_entries": len(df),
        "num_genera": len(df["genus"].unique())
    }
    with open("database/summary_statistics.json", "w") as f:
        f.write(json.dumps(summary_statistics))

    # Update taxonomic tree
    generate_tree(df[df['NCBI taxid'].notna()]['NCBI taxid'])

    # Calling the nextflow script
    task_summarize_nextflow.delay()

    # Calculate checksum for the database
    checksum = calculate_checksum("database/summary.json")
    with open("database/summary.json.sha256", "w") as f:
        f.write(checksum)
    return "Done"


@celery_instance.task(time_limit=20000)
def task_summarize_nextflow():
    # Trying to cleanup the work folder
    try:
        if not dev_mode:
            os.system("rm -rf /app/workflows/idbac_summarize_database/work")
    except:
        pass

    # Now we'll call the NextFlow Script

    if dev_mode:
        cmd = "cd /workflows/idbac_summarize_database/ && \
        nextflow run /workflows/idbac_summarize_database/nf_workflow.nf \
        --input_database /database/summary.json \
        -profile docker \
        -c workflows/idbac_summarize_database/nextflow.config"
    else:
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