#!/usr/bin/env python3

import click
from schematic.manifest.generator import ManifestGenerator
from schematic import CONFIG

CONTEXT_SETTINGS = dict(help_option_names=['--help', '-h'])  # help options

# invoke_without_command=True -> forces the application not to show aids before losing them with a --h
@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
def manifest(): # use as `schematic manifest ...`
    """
    Sub-commands with Manifest Generation utilities/methods.
    """
    pass


# prototype based on getModelManifest() and get_manifest()
# use as `schematic config get positional_args --optional_args`
@manifest.command('get', short_help='Prepares the manifest URL based on provided schema.')
# define the optional arguments
@click.option('-t', '--title', help='Title of generated manifest file.')
@click.option('-d', '--data_type', help='Data type/component from JSON-LD schema to be used for manifest generation.')
@click.option('-p', '--path_to_json_ld', help='Path to JSON-LD schema.')
@click.option('-d', '--dataset_id', help='SynID of existing dataset on Synapse.')
@click.option('-s', '--sheet_url', type=bool, help='Enable/disable URL generation.')
@click.option('-j', '--json_schema', help='Path to JSON Schema (validation schema).')
@click.option('-c', '--config', help='Path to schematic configuration file.')
def get_manifest(title, data_type, path_to_json_ld, 
                 dataset_id, sheet_url, json_schema, 
                 config):
    """
    Running CLI with manifest generation options.
    """
    config_data = CONFIG.load_config(config)

    # optional parameters that need to be passed to ManifestGenerator()
    # can be read from config.yml as well
    if title is None:
        TITLE = CONFIG["manifest"]["title"]
        click.echo("TITLE argument is being read from config file.")
    else:
        TITLE = title

    if data_type is None:
        DATA_TYPE = CONFIG["manifest"]["data_type"]
        click.echo("TITLE argument is being read from config file.")
    else:
        DATA_TYPE = data_type

    if path_to_json_ld is None:
        click.echo("PATH_TO_JSON_LD argument is being read from config file.")
        PATH_TO_JSON_LD = CONFIG["model"]["input"]["location"]
    else:
        PATH_TO_JSON_LD = path_to_json_ld

    if json_schema is None:
        click.echo("JSON_SCHEMA argument is being read from config file.")
        JSON_SCHEMA = CONFIG["model"]["input"]["validation_schema"]
    else:
        JSON_SCHEMA = json_schema

    # create object of type ManifestGenerator
    manifest_generator = ManifestGenerator(title=TITLE, 
                                           path_to_json_ld=PATH_TO_JSON_LD, 
                                           root=DATA_TYPE)
        
    # call get_manifest() on manifest_generator
    click.echo(manifest_generator.get_manifest(dataset_id=dataset_id, 
                                               sheet_url=sheet_url, 
                                               json_schema=JSON_SCHEMA))
