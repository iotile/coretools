"""This file contains the schema verifier for verifying a recipe file."""

from iotile.core.utilities.schema_verify import (DictionaryVerifier, Verifier, StringVerifier, IntVerifier, ListVerifier,
                                                 OptionsVerifier, BooleanVerifier)


ActionItem = DictionaryVerifier(desc="A description of a single action that should be run")
ActionItem.add_required("name", StringVerifier("The name of the action type that should be executed"))
ActionItem.add_optional("description", StringVerifier("A short description for what the action is doing"))
ActionItem.add_optional("use", ListVerifier(StringVerifier("The name of a resource"), desc="A list of used resources"))
ActionItem.add_optional("open_before", ListVerifier(StringVerifier("The name of a resource"), desc="A list of resources to open before this step"))
ActionItem.add_optional("close_after", ListVerifier(StringVerifier("The name of a resource"), desc="A list of resources to close after this step"))
ActionItem.key_rule(None, Verifier("A parameter passed into the underlying action"))  # Allow any additional values

ResourceItem = DictionaryVerifier(desc="A shared resource that can be used by one or more action steps")
ResourceItem.add_required("name", StringVerifier("The name of the resource so it can be referenced in a step"))
ResourceItem.add_required("type", StringVerifier("A unique string identifying what type of resource should be created"))
ResourceItem.add_optional("autocreate", BooleanVerifier(desc="Whether to automatically open the resource before the recipe and close it after the recipe"))
ResourceItem.key_rule(None, Verifier("A parameter passed into the underlying resouce"))  # Allow any additional values

VariableDefault = DictionaryVerifier(desc="A default value for a variable", fixed_length=1)
VariableDefault.key_rule(None, StringVerifier())

RecipeSchema = DictionaryVerifier(desc="A recipe containing a list of actions")
RecipeSchema.add_optional("name", StringVerifier("A descriptive name for this recipe"))
RecipeSchema.add_required("description", StringVerifier("A description of what the recipe does"))
RecipeSchema.add_optional("idempotent", BooleanVerifier(desc="Whether the recipe can be run multiple times without breaking"))
RecipeSchema.add_required("actions", ListVerifier(ActionItem.clone(), min_length=1, desc="A list of steps to perform to realize this recipe"))
RecipeSchema.add_optional("resources", ListVerifier(ResourceItem.clone(), desc="An optional list of shared resources to setup"))
RecipeSchema.add_optional("defaults", ListVerifier(VariableDefault.clone(), desc="An optional list of default values for free recipe variables"))
