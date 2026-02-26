# ABEL-Processor
The purpose of this repo is to provide a set of scripts to process ABEL output into files more suited for onboarding. Timeout errors are very common for even moderate sized files; this set of scripts processes the ABEL output into config files containing a single device, as a workaround to avoid timeout errors. 

Usage:

1) Generate an ABEL config file like usual
2) Navigate to this repository in the terminal
3) Run the following command: python3 process_ABEL_output.py
4) This command will generate three subfolders in the same directory as the ABEL export, called update_reporting_entities, update_virtual_entities, and add_virtual_entities
5) To onboard the config files in these subfolders, run python3 execute_API_calls_series.py
6) A results folder will be generated, containing the onboarding operation results for each config file onboarded
