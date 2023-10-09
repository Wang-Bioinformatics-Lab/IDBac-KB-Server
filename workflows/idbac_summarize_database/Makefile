run:
	nextflow run ./nf_workflow.nf -resume --input_database ../../database/depositions/

run_hpcc:
	nextflow run ./nf_workflow.nf -resume -c nextflow_hpcc.config

run_docker:
	nextflow run ./nf_workflow.nf -resume -with-docker <CONTAINER NAME>