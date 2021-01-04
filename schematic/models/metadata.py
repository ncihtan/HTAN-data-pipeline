import pandas as pd
import networkx as nx
import json
import re
import synapseclient
from jsonschema import Draft7Validator, exceptions, validate, ValidationError

# allows specifying explicit variable types
from typing import Any, Dict, Optional, Text, List

# handle schema logic; to be refactored as SchemaExplorer matures into a package
# as collaboration with Biothings progresses

from schematic.schemas.explorer import SchemaExplorer
from schematic.manifest.generator import ManifestGenerator
from schematic.schemas.generator import SchemaGenerator
from schematic.synapse.store import SynapseStorage

class MetadataModel(object):
    """Metadata model wrapper around schema.org specification graph.
    
    Provides basic utilities to:

    1) manipulate the metadata model
    2) generate metadata model views:
        - generate manifest view of the metadata model
        - generate validation schema view of the metadata model
    """

    def __init__(self,
                inputMModelLocation: str,
                inputMModelLocationType: str,
                ) -> None:

        """Instantiates a MetadataModel object.

        Args:
            inputMModelLocation: local path, uri, synapse entity id (e.g. gs://, syn123, /User/x/…); present location
            inputMModelLocationType: specifier to indicate where the metadata model resource can be found (e.g. 'local' if file/JSON-LD is on local machine)
        """
        # extract extension of 'inputMModelLocation'
        # ensure that it is necessarily pointing to a '.jsonld' file
        if inputMModelLocation.rpartition('.')[-1] == "jsonld":
            self.inputMModelLocation = inputMModelLocation

            self.sg = SchemaGenerator(inputMModelLocation)
        else:
            print("Can't create object of SchemaGenerator class. Please make sure the 'inputMModelLocation' argument is pointing to a JSON-LD file.")
            return

        # check if the type of MModel file is "local"
        # currently, the application only supports reading from local JSON-LD files
        if inputMModelLocationType == "local":
            self.inputMModelLocationType = inputMModelLocationType
        else:
            print("Please make sure to use a local JSON-LD file. 'InputMModelLocationType' must be 'local'.")
            return

    # business logic: expose metadata model "views" depending on "controller" logic
    # (somewhat analogous to Model View Controller pattern for GUI/web applications)
    # i.e. jsonschemas, annotation manifests, metadata/annotation dictionary web explorer
    # are all "views" of the metadata model.
    # The "business logic" in this MetadataModel class provides functions exposing relevant parts
    # of the metadata model needed so that these views can be generated by user facing components;
    # controller components are (loosely speaking) responsible for handling the interaction between views and the model
    # some of these components right now reside in the Bundle class

    def getModelSubgraph(self, rootNode: str, 
                        subgraphType: str) -> nx.DiGraph:
        """Gets a schema subgraph from rootNode descendants based on edge/node properties of type subgraphType.
        
        Args:
            rootNode: a schema node label (i.e. term).
            subgraphType: the kind of subgraph to traverse (i.e. based on node properties or edge labels).
        
        Returns:
            A directed subgraph (networkx DiGraph) of the metadata model with vertex set root node descendants.

        Raises: 
            ValueError: rootNode not found in metadata model.
        """
        pass

    def getOrderedModelNodes(self, rootNode: str, relationshipType: str) -> List[str]:
        """Get a list of model objects ordered by their topological sort rank in a model subgraph on edges of a given relationship type.

        Args:
            rootNode: a schema object/node label (i.e. term)
            relationshipType: edge label type of the schema subgraph (e.g. requiresDependency)
        
        Returns:
            An ordered list of objects, that are all descendants of rootNode.

        Raises: 
            ValueError: rootNode not found in metadata model.
        """
        ordered_nodes = self.sg.get_descendants_by_edge_type(rootNode, relationshipType, connected=True, ordered=True)

        ordered_nodes.reverse()

        return ordered_nodes

    
    def getModelManifest(self, title: str, rootNode: str, jsonSchema: str = None, filenames: list = None) -> str: 
        """Gets data from the annotations manifest file.

        TBD: Does this method belong here or in manifest generator?
        
        Args:
            rootNode: a schema node label (i.e. term).
        
        Returns:
            A manifest URI (assume Google doc for now).

        Raises: 
            ValueError: rootNode not found in metadata model.
        """
        additionalMetadata = {}
        if filenames:
            additionalMetadata["Filename"] = filenames

        try:
            mg = ManifestGenerator(title, self.inputMModelLocation, rootNode, additionalMetadata)
        except ValueError:
            print("rootNode not found in metadata model.")
            return
        except:
            print("There was a problem retrieving the manifest.")
            return

        if jsonSchema:
            return mg.get_manifest(json_schema=jsonSchema)

        return mg.get_manifest()


    def get_component_requirements(self, source_component: str) -> List[str]:
        """Given a source model component (see https://w3id.org/biolink/vocab/category for definnition of component), return all components required by it.
        Useful to construct requirement dependencies not only between specific attributes but also between categories/components of attributes;
        Can be utilized to track metadata completion progress across multiple categories of attributes.
        
        Args: 
            source_component: an attribute label indicating the source component.

        Returns: 
            A list of required components associated with the source component.
        """ 
        # get metadata model schema graph
        # mm_graph = self.se.get_nx_schema()

        # get required components for the input/source component
        req_components = self.sg.get_component_requirements(source_component)
        # req_components = get_component_requirements(mm_graph, source_component) 

        return req_components


    # TODO: abstract validation in its own module
    def validateModelManifest(self, manifestPath: str, rootNode: str, jsonSchema: str = None) -> List[str]:     
        """Check if provided annotations manifest dataframe satisfies all model requirements.

        Args:
            rootNode: a schema node label (i.e. term).
            manifestPath: a path to the manifest csv file containing annotations.
        
        Returns:
            A validation status message; if there is an error the message.
            contains the manifest annotation record (i.e. row) that is invalid, along with the validation error associated with this record.
        
        Raises: 
            ValueError: rootNode not found in metadata model.
        """
        # get validation schema for a given node in the data model, if the user has not provided input validation schema
        if not jsonSchema:
            jsonSchema = self.sg.get_json_schema_requirements(rootNode, rootNode + "_validation")
         
        errors = []
 
        # get annotations from manifest (array of json annotations corresponding to manifest rows)
        manifest = pd.read_csv(manifestPath).fillna("")


        """ 
        check if each of the provided annotation columns has validation rule 'list'
        if so, assume annotation for this column are comma separated list of multi-value annotations
        convert multi-valued annotations to list
        """
        for col in manifest.columns:
            
            # remove trailing/leading whitespaces from manifest
            manifest.applymap(lambda x: x.strip() if isinstance(x, str) else x)


            # convert manifest values to string
            # TODO: when validation handles annotation types as validation rules 
            # would have to avoid converting everything to string
            manifest[col] = manifest[col].astype(str)

            # if the validation rule is set to list, convert items in the
            # annotations manifest to a list and strip each value from leading/trailing spaces
            if "list" in self.sg.get_node_validation_rules(col): 
                manifest[col] = manifest[col].apply(lambda x: [s.strip() for s in str(x).split(",")])

        annotations = json.loads(manifest.to_json(orient='records'))
        for i, annotation in enumerate(annotations):
            v = Draft7Validator(jsonSchema)

            for error in sorted(v.iter_errors(annotation), key=exceptions.relevance):
                errorRow = i + 2
                errorCol = error.path[-1] if len(error.path) > 0 else "Wrong schema" 
                errorMsg = error.message[0:500]
                errorVal = error.instance if len(error.path) > 0 else "Wrong schema"

                errors.append([errorRow, errorCol, errorMsg, errorVal])
                
        return errors


    def populateModelManifest(self, title, manifestPath: str, rootNode: str) -> str: 
        """Populate an existing annotations manifest based on a dataframe.
         
        Args:
            rootNode: a schema node label (i.e. term).
            manifestPath: a path to the manifest csv file containing annotations.
        
        Returns:
            A link to the filled in model manifest (e.g. google sheet).

        Raises: 
            ValueError: rootNode not found in metadata model.
        """
        mg = ManifestGenerator(title, self.inputMModelLocation, rootNode)
        
        emptyManifestURL = mg.get_manifest()

        return mg.populate_manifest_spreadsheet(manifestPath, emptyManifestURL)


    def submit_metadata_manifest(self, manifest_path: str, dataset_id: str, validate_component: str = None) -> bool:
        """Wrap methods that are responsible for validation of manifests for a given component, and association of the 
        same manifest file with a specified dataset.
        Args:
            manifest_path: Path to the manifest file, which contains the metadata.
            dataset_id: Synapse ID of the dataset on Synapse containing the metadata manifest file.
            validate_component: Component from the schema.org schema based on which the manifest template has been generated.
        Returns:
            True: If both validation and association were successful.
        Exceptions:
            ValueError: When validate_component is provided, but it cannot be found in the schema.
            ValidationError: If validation against data model was not successful.
        """
        syn_store = SynapseStorage()

        # check if user wants to perform validation or not
        if validate_component is not None:

            try:
                # check if the component ("class" in schema) passed as argument is valid (present in schema) or not
                self.sg.se.is_class_in_schema(validate_component)
            except:
                # a KeyError exception is raised when validate_component fails in the try-block above
                # here, we are suppressing the KeyError exception and replacing it with a more
                # descriptive ValueError exception
                raise ValueError("The component {} could not be found "
                                 "in the schema.".format(validate_component))

            # automatic JSON schema generation and validation with that JSON schema
            val_errors = self.validateModelManifest(manifestPath=manifest_path, rootNode=validate_component)

            # if there are no errors in validation process
            if not val_errors:
                
                # upload manifest file from `manifest_path` path to entity with Syn ID `dataset_id` 
                syn_store.associateMetadataWithFiles(metadataManifestPath=manifest_path, datasetId=dataset_id)

                print("No validation errors resulted during association.")
                return True
            else:
                print(val_errors)
                raise ValidationError("Manifest could not be validated under provided data model.")

        # no need to perform validation, just submit/associate the metadata manifest file
        syn_store.associateMetadataWithFiles(metadataManifestPath=manifest_path, datasetId=dataset_id)

        print("Validation was not performed on manifest file before association.")
        
        return True
        