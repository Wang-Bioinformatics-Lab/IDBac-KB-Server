import dash
from dotenv import dotenv_values
from flask import request
from flask import send_from_directory, send_file
import glob
import json
import pandas as pd
import os
import yaml


import tasks
from utils import convert_to_mzml

from flask import Blueprint
api_blueprint = Blueprint('api_blueprint', __name__)

_env = dotenv_values()

dev_mode = False
if not os.path.isdir('/app'):
    dev_mode =  True

@api_blueprint.route("/api")
def api():
    return "Up"

@api_blueprint.route("/api/database/refresh", methods=["GET"])
def refresh():
    # Calling task to summarize and update the catalog
    tasks.task_summarize_depositions.delay()

    return "Refreshing"

@api_blueprint.route("/api/get_all_strain_names", methods=["GET"])
def get_all_strain_names():
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")

    return json.dumps(summary_df["Strain name"].tolist())

@api_blueprint.route("/api/spectrum", methods=["POST"])
def deposit():
    # Check the API credentials
    assert("CREDENTIALSKEY" in _env)
    request_credentials = request.values.get("CREDENTIALSKEY")

    if request_credentials != _env["CREDENTIALSKEY"]:
        return "Invalid Credentials", 403

    # Getting all the parameter arguments
    all_parameters = list(request.values.keys())

    spectrum_dict = json.loads(request.values.get("spectrum_json"))
    spectrum_dict["task"] = request.values.get("task")
    spectrum_dict["user"] = request.values.get("user")

    # Saving the results here
    task_result = tasks.task_deposit_data.delay(spectrum_dict, None)

    # Enable this call to be blocking
    return "DONE"

@api_blueprint.route("/api/db-checksum", methods=["GET"])
def checksum():
    if dev_mode:
        return send_from_directory("workflows/idbac_summarize_database/nf_output/", "idbac_database.json.sha256")
    else:
        return send_from_directory("/app/workflows/idbac_summarize_database/nf_output/", "idbac_database.json.sha256")

@api_blueprint.route("/api/spectrum", methods=["GET"])
def download():
    # Getting a single spectrum
    database_id = request.values.get("database_id")

    if database_id == "ALL":
        if dev_mode:
            return send_from_directory("workflows/idbac_summarize_database/nf_output/", "idbac_database.json")
        else:
            return send_from_directory("/app/workflows/idbac_summarize_database/nf_output/", "idbac_database.json")

    # Finding all the database files
    database_files = glob.glob("database/depositions/**/{}.json".format(os.path.basename(database_id)))

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    
    return send_from_directory(os.path.dirname(database_files[0]), os.path.basename(database_files[0]))

@api_blueprint.route("/api/spectrum/mzml-raw", methods=["GET"])
def download_mzml_raw():
    # Get the database_id from the request
    database_id = request.args.get("database_id")
    
    if not database_id:
        return "Database ID is required", 400

    # Find the corresponding JSON file for the database ID
    database_files = glob.glob(f"database/depositions/**/{os.path.basename(database_id)}.json")

    if len(database_files) == 0:
        return "File not found", 404

    if len(database_files) > 1:
        return "Multiple files found", 500
    
    # Convert the file to mzML format
    mzml_bytes = convert_to_mzml(database_files[0])

    # Return the mzML bytes as a downloadable file
    mzml_bytes.seek(0)
    return send_file(
        mzml_bytes,
        as_attachment=True,
        download_name=f"{database_id}.mzML",
        mimetype="application/octet-stream"
    )

@api_blueprint.route("/api/spectrum/mzml-filtered", methods=["GET"])
def download_mzml_filtered():
    # Getting a single spectrum
    database_id = request.values.get("database_id")
    bin_width   = request.values.get("bin_width", 10)

    # Finding all the database files
    database_files = f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{os.path.basename(database_id)}.json"

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    
    # Get the file and convert to mzML
    mzml_bytes  = convert_to_mzml(database_files[0])

    # Return bytes as file
    mzml_bytes.seek(0)
    return send_file(
        mzml_bytes,
        as_attachment=True,
        download_name=f"{database_id}.mzML",
        mimetype="application/octet-stream"
    )


@api_blueprint.route("/api/spectrum/filtered", methods=["GET"])
def filtered_spectra():
    # Getting a single spectrum
    database_id = request.values.get("database_id")
    bin_width   = request.values.get("bin_width", 10)

    if database_id == "ALL":
        if dev_mode:
            return send_from_directory(f"workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/", "output_merged_spectra.json")
        else:
            return send_from_directory(f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/", "output_merged_spectra.json")

    # Finding all the database files
    database_files = glob.glob(f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{os.path.basename(database_id)}.json")

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    
    return send_from_directory(os.path.dirname(database_files[0]), os.path.basename(database_files[0]))

@api_blueprint.route("/api/spectrum/ml_db", methods=["GET"])
def ml_db():    # http://localhost:5392/api/spectrum/ml_db
    # Getting a single spectrum
    database_id = request.values.get("database_id", 'ALL')

    if database_id == "ALL":
        if dev_mode:
            return send_from_directory("workflows/idbac_summarize_database/nf_output/ml_db/", "idbac_ml_db.json")
        else:
            return send_from_directory("/app/workflows/idbac_summarize_database/nf_output/ml_db/", "idbac_ml_db.json")
        
    else:
        # Return an error if the database_id is not "ALL"
        return "Only 'ALL' is supported for ml_db", 400

@api_blueprint.route("/api/spectra", methods=["GET"])
def spectra_list():
    # Parse summary
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")

    # return json
    return summary_df.to_json(orient="records")

@api_blueprint.route("/admin/nextflow_report", methods=["GET"])
def nextflow_report():
    if dev_mode:
        if os.path.exists("workflows/idbac_summarize_database/IDBac_summarize_database_report.html"):
            return send_from_directory("workflows/idbac_summarize_database", "IDBac_summarize_database_report.html")
        else:
            return "No Report Found", 404
    else:
        if os.path.exists("/app/workflows/idbac_summarize_database/IDBac_summarize_database_report.html"):
            return send_from_directory("/app/workflows/idbac_summarize_database", "IDBac_summarize_database_report.html")
        else:
            return "No Report Found", 404
        
@api_blueprint.route("/analysis-utils/get_genus_options", methods=["GET"])
def analysis_utils_get_genus_options():
    # TODO: Make more general to handle other columns
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")
    genus_options = summary_df.loc[summary_df.genus.notna(), 'genus'].unique().tolist()

    # Format as Key: Value JSON
    genus_options = [{"value-key": str(genus), "display-key": str(genus).capitalize()} for genus in genus_options]
    return json.dumps(genus_options)

@api_blueprint.route("/analysis-utils/get_species_options", methods=["GET"])
def analysis_utils_get_species_options():
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")
    species_options = summary_df.loc[summary_df.species.notna(), 'species'].unique().tolist()

    # Format as Key: Value JSON
    species_options = [{"value-key": str(species), "display-key": str(species).capitalize()} for species in species_options]
    return json.dumps(species_options)

@api_blueprint.route("/analysis-utils/get_instrument_options", methods=["GET"])
def analysis_utils_get_instrument_options():
    # Load the workflow yaml file
    with open("workflows/idbac_summarize_database/bin/inst_peak_filtration.yml", "r", encoding='utf-8') as f:
        config = yaml.safe_load(f)
        print(config, flush=True)

        # Reformat keys as a json list with "value" and "display" keys
        keys = (config.keys())
        out = []
        for key in keys:
            out.append({
                    "value": key,
                    "display": key.replace("_", " ").title().replace("Maldi", "MALDI").replace("Ms", "MS")
            })

        return json.dumps(out)

@api_blueprint.route("/analysis-utils/get_instrument_config", methods=["GET"])
def analysis_utils_get_instrument_config():
    if os.path.exists("workflows/idbac_summarize_database/bin/inst_peak_filtration.yml"):
        return send_from_directory("workflows/idbac_summarize_database/bin", "inst_peak_filtration.yml")
    else:
        return "No Config Found", 404

@api_blueprint.route("/download_tree_png", methods=["GET"])
def download_tree_png():
    if dev_mode:
        if os.path.exists("workflows/idbac_summarize_database/nf_output/tree.png"):
            return send_from_directory("workflows/idbac_summarize_database/nf_output", "tree.png")
        else:
            return "No Image Found", 404
    else:
        if os.path.exists("/app/assets/tree.png"):
            return send_from_directory("/app/assets", "tree.png")
        else:
            return "No Image Found", 404

@api_blueprint.route("/download_tree_svg", methods=["GET"])
def download_tree_svg():
    if dev_mode:
        if os.path.exists("workflows/idbac_summarize_database/nf_output/tree.svg"):
            return send_from_directory("workflows/idbac_summarize_database/nf_output", "tree.svg")
        else:
            return "No Image Found", 404
    else:
        if os.path.exists("/app/assets/tree.svg"):
            return send_from_directory("/app/assets", "tree.svg")
        else:
            return "No Image Found", 404
    
@api_blueprint.route("/download_tree_nwk", methods=["GET"])
def download_tree_nwk():
    if dev_mode:
        if os.path.exists("workflows/idbac_summarize_database/nf_output/tree.nwk"):
            return send_from_directory("workflows/idbac_summarize_database/nf_output", "tree.nwk")
        else:
            return "No Image Found", 404
    else:
        if os.path.exists("/app/assets/tree.nwk"):
            return send_from_directory("/app/assets", "tree.nwk")
        else:
            return "No Image Found", 404