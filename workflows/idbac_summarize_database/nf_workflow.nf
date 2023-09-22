#!/usr/bin/env nextflow
nextflow.enable.dsl=2

params.input_database = ""

TOOL_FOLDER = "$baseDir/bin"


process formatDatabase {
    publishDir "./nf_output", mode: 'copy'

    conda "$TOOL_FOLDER/conda_env.yml"

    input:
    file idbac_database_folder

    output:
    file 'idbac_database.json'
    file 'idbac_database_scanmapping.tsv'
    file 'idbac_database.mzML'

    """
    python $TOOL_FOLDER/format_database.py \
    $idbac_database_folder \
    idbac_database.json \
    idbac_database_scanmapping.tsv \
    temp.mzML

    export LC_ALL=C && $TOOL_FOLDER/msconvert temp.mzML \
    --mzML --32 --outfile idbac_database.mzML
    """
}

process baselineCorrection2 {
    publishDir "./nf_output/library", mode: 'copy'

    conda "$TOOL_FOLDER/conda_maldiquant.yml"

    input:
    file input_file 

    output:
    file 'baselinecorrected/*.mzML'

    """
    mkdir baselinecorrected
    Rscript $TOOL_FOLDER/baselineCorrection.R $input_file baselinecorrected/${input_file}
    """
}

process mergeSpectra {
    publishDir "./nf_output", mode: 'copy'

    conda "$TOOL_FOLDER/conda_env.yml"

    input:
    file idbac_database_mzML
    file idbac_database_scan_mapping

    output:
    file 'output_database.mgf' optional true
    file 'output_mapping.tsv' optional true

    """
    python $TOOL_FOLDER/merge_spectra.py \
    $idbac_database_mzML \
    $idbac_database_scan_mapping \
    output_database.mgf \
    output_mapping.tsv
    """
}

// TODO: We need to merge the full summary with the scan mapping so we know the scan number to show in the summary

workflow {
    database_folder_ch = Channel.fromPath(params.input_database)

    // Downloading Database
    (output_idbac_database_ch, output_scan_mapping_ch, output_idbac_mzML_ch) = formatDatabase(database_folder_ch)

    // Baseline Correct the spectra
    baseline_corrected_database_mzML_ch = baselineCorrection2(output_idbac_mzML_ch)

    // Merging the database spectra
    mergeSpectra(baseline_corrected_database_mzML_ch, output_scan_mapping_ch)
}