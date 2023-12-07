from celery import Celery
import glob
import sys
import os
import json
from ulid import ULID
import pandas as pd
import requests
import xmltodict

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

@celery_instance.task(time_limit=3600)
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

    # We can go and get Taxonomy information from the NCBI API
    for spectra_entry in spectra_list:
        try:
            genbank_accession = spectra_entry["Genbank accession"]

            # Updating the URL
            mapping_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=nucleotide&db=nucleotide&id={}&rettype=gb&retmode=xml".format(genbank_accession)

            r = requests.get(mapping_url)
            result_dictionary = xmltodict.parse(r.text)
            
            try:
                nuccore_id = result_dictionary["eLinkResult"]["LinkSet"][0]["IdList"]["Id"]
            except:
                nuccore_id = result_dictionary["eLinkResult"]["LinkSet"]["IdList"]["Id"]

            # here we will use an API to get the information
            xml_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={}&retmode=xml".format(nuccore_id)

            r = requests.get(xml_url)
            result_dictionary = xmltodict.parse(r.text)

            # Getting taxonomy
            taxonomy = result_dictionary["GBSet"]["GBSeq"]["GBSeq_taxonomy"]
            organism = result_dictionary["GBSet"]["GBSeq"]["GBSeq_organism"]

            spectra_entry["FullTaxonomy"] = taxonomy + "; " + organism
        except:
            pass


    # Summarizing
    df = pd.DataFrame(spectra_list)

    

    # Saving the summary
    df.to_csv("database/summary.tsv", index=False, sep="\t")

    # Trying to cleanup the work folder
    try:
        os.system("rm -rf /app/workflows/idbac_summarize_database/work")
    except:
        pass

    # Now we'll call the NextFlow Script

    cmd = "cd /app/workflows/idbac_summarize_database/ && \
    nextflow run /app/workflows/idbac_summarize_database/nf_workflow.nf \
    --input_database /app/database/depositions \
    -profile docker"

    os.system(cmd)

    # Then we need to copy the files back from the right location
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