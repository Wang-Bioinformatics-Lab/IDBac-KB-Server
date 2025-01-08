#!/usr/bin/env nextflow
nextflow.enable.dsl=2

TOOL_FOLDER = "$baseDir/bin"

process mergeSpectra {
    conda "$TOOL_FOLDER/conda_env.yml"

    publishDir "${params.output_dir}", mode: 'copy'

    input:
    file idbac_database_mzML
    file idbac_database_scan_mapping
    val bin_size

    output:
    file 'output_database.mgf' optional true
    file 'output_mapping.tsv' optional true
    file 'output_spectra_json' optional true

    """
    mkdir output_spectra_json
    python $TOOL_FOLDER/merge_spectra.py \
    $idbac_database_mzML \
    $idbac_database_scan_mapping \
    output_database.mgf \
    output_mapping.tsv \
    output_spectra_json \
    --bin_size ${bin_size}
    """
}

process prepareOutput {
    conda "$TOOL_FOLDER/conda_env.yml"

    publishDir "${params.output_dir}", mode: 'copy'

    input:
    file idbac_full_spectra_json
    file idbac_merged_spectra_json_folder

    output:
    file 'output_merged_spectra.json' optional true

    """
    python $TOOL_FOLDER/create_consolidated_merged_spectra.py \
    $idbac_full_spectra_json \
    $idbac_merged_spectra_json_folder \
    output_merged_spectra.json
    """
}

workflow MergeAndOutput {
    take:
    baseline_corrected_database_mzML_ch
    output_scan_mapping_ch
    output_idbac_database_ch
    bin_size

    main:
    // Merging the database spectra
    (output_database_mgf, output_mapping_tsv, merged_json_folder_ch) = mergeSpectra(baseline_corrected_database_mzML_ch, output_scan_mapping_ch, bin_size)

    // Consolidating the merged output
    output_merged_spectra_json = prepareOutput(output_idbac_database_ch, merged_json_folder_ch)

    // Very unclear why this isn't working.
    // publish:
    // output_database_mgf >> "${params.output_dir}"
    // output_mapping_tsv >> "${params.output_dir}"
    // merged_json_folder_ch >> "${params.output_dir}"
    // output_merged_spectra_json >> "${params.output_dir}"

}