import time
from collections import namedtuple
from string import Template
import re
import os
import sys
import zipfile
import tempfile
from iotile.core.exceptions import ArgumentError, ValidationError
from .exceptions import RecipeFileInvalid, UnknownRecipeActionType, RecipeVariableNotPassed, UnknownRecipeResourceType, RecipeResourceManagementError
from .recipe_format import RecipeSchema

ResourceDeclaration = namedtuple("ResourceDeclaration", ["name", "type", "args", "autocreate", "description", "type_name"])
ResourceUsage = namedtuple("ResourceUsage", ["used", "opened", "closed"])
RecipeStep = namedtuple("RecipeStep", ["factory", "args", "resources", "fixed_files"])

TEMPLATE_REGEX = r"((?<!\$)|(\$\$)+)\$({(?P<long_id>[a-zA-Z_]\w*)}|(?P<short_id>[a-zA-Z_]\w*))"


class RecipeObject:
    """An object representing a fixed set of processing steps.

    RecipeObjects are used to create and run production operations
    that need to be controlled and repeatable with no room for error.

    Args:
        name (str): The name of the recipe
        description (str): A textual description of what the recipe
            does.
        steps (list of RecipeStep): A list of steps that will be performed
            every time the recipe is executed. The execution will proceed in
            two steps, first all the steps will be combined with their
            dictionary of parameters and verified.  Then each step will be
            executed in order.
        resources (list of (ResourceObject-like, dict)): A list of resources that
            can be shared between steps.  A resource is something like a database
            connection or a connected HardwareManager object that can be usefully
            reused by multiple steps.
        defaults (dict of key to default value): A dictionary of default variable
            values that should be used if not set during a run.
        path (str): The path to the original yaml file that this recipe was loaded
            from.
    """

    def __init__(self, name, description=None, steps=None, resources=None, defaults=None, path=None):
        if steps is None:
            steps = []

        if resources is None:
            resources = []

        if defaults is None:
            defaults = []

        self.steps = steps

        self.name = name
        self.description = description
        self.resources = resources
        self.defaults = defaults
        self.path = path

        if path is not None:
            self.run_directory = os.path.dirname(path)
        else:
            self.run_directory = os.getcwd()

        self.free_variables = set()
        self.external_files = False

        for _factory, args, _resources, files in steps:
            self.free_variables |= _extract_variables(args)
            if len(files) > 0:
                self.external_files = True

        for decl in resources.values():
            self.free_variables |= _extract_variables(decl.args)

        default_names = set(self.defaults)
        if not default_names <= self.free_variables:
            raise RecipeFileInvalid("Default variables specified but not used", recipe=name, extra_defaults=default_names - self.free_variables)

        self.required_variables = self.free_variables - default_names
        self.optional_variables = self.free_variables - self.required_variables

    def archive(self, output_path):
        """Archive this recipe and all associated files into a .ship archive.

        Args:
            output_path (str): The path where the .ship file should be saved.
        """

        if self.path is None:
            raise ArgumentError("Cannot archive a recipe yet without a reference to its original yaml file in self.path")

        outfile = zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED)

        outfile.write(self.path, arcname="recipe_script.yaml")

        written_files = set()

        for _factory, args, _resources, files in self.steps:
            for arg_name in files:
                file_path = args[arg_name]

                if file_path in written_files:
                    continue

                if os.path.basename(file_path) != file_path:
                    raise ArgumentError("Cannot archive a recipe yet that references file not in the same directory as the recipe")

                full_path = os.path.join(os.path.dirname(self.path), file_path)
                outfile.write(full_path, arcname=file_path)
                written_files.add(file_path)

    @classmethod
    def FromArchive(cls, path, actions_dict, resources_dict, temp_dir=None):
        """Create a RecipeObject from a .ship archive.

        This archive should have been generated from a previous call to
        iotile-ship -a <path to yaml file>

        or via iotile-build using autobuild_shiparchive().

        Args:
            path (str): The path to the recipe file that we wish to load
            actions_dict (dict): A dictionary of named RecipeActionObject
                types that is used to look up all of the steps listed in
                the recipe file.
            resources_dict (dict): A dictionary of named RecipeResource types
                that is used to look up all of the shared resources listed in
                the recipe file.
            file_format (str): The file format of the recipe file.  Currently
                we only support yaml.
            temp_dir (str): An optional temporary directory where this archive
                should be unpacked. Otherwise a system wide temporary directory
                is used.
        """

        if not path.endswith(".ship"):
            raise ArgumentError("Attempted to unpack a recipe archive from a file that did not end in .ship", path=path)

        name = os.path.basename(path)[:-5]

        if temp_dir is None:
            temp_dir = tempfile.mkdtemp()

        extract_path = os.path.join(temp_dir, name)
        archive = zipfile.ZipFile(path, "r")
        archive.extractall(extract_path)

        recipe_yaml = os.path.join(extract_path, 'recipe_script.yaml')
        return cls.FromFile(recipe_yaml, actions_dict, resources_dict, name=name)

    @classmethod
    def FromFile(cls, path, actions_dict, resources_dict, file_format="yaml", name=None):
        """Create a RecipeObject from a file.

        The file should be a specially constructed yaml file that describes
        the recipe as well as the actions that it performs.

        Args:
            path (str): The path to the recipe file that we wish to load
            actions_dict (dict): A dictionary of named RecipeActionObject
                types that is used to look up all of the steps listed in
                the recipe file.
            resources_dict (dict): A dictionary of named RecipeResource types
                that is used to look up all of the shared resources listed in
                the recipe file.
            file_format (str): The file format of the recipe file.  Currently
                we only support yaml.
            name (str): The name of this recipe if we created it originally from an
                archive.
        """

        format_map = {
            "yaml": cls._process_yaml
        }

        format_handler = format_map.get(file_format)
        if format_handler is None:
            raise ArgumentError("Unknown file format or file extension", file_format=file_format, \
                known_formats=[x for x in format_map if format_map[x] is not None])
        recipe_info = format_handler(path)

        if name is None:
            name, _ext = os.path.splitext(os.path.basename(path))

        # Validate that the recipe file is correctly formatted
        try:
            recipe_info = RecipeSchema.verify(recipe_info)
        except ValidationError as exc:
            raise RecipeFileInvalid("Recipe file does not match expected schema", file=path, error_message=exc.msg, **exc.params)

        description = recipe_info.get('description')

        # Parse out global default and shared resource information
        try:
            resources = cls._parse_resource_declarations(recipe_info.get('resources', []), resources_dict)
            defaults = cls._parse_variable_defaults(recipe_info.get("defaults", []))

            steps = []
            for i, action in enumerate(recipe_info.get('actions', [])):
                action_name = action.pop('name')
                if action_name is None:
                    raise RecipeFileInvalid("Action is missing required name parameter", \
                        parameters=action, path=path)

                action_class = actions_dict.get(action_name)
                if action_class is None:
                    raise UnknownRecipeActionType("Unknown step specified in recipe", \
                        action=action_name, step=i + 1, path=path)

                # Parse out any resource usage in this step and make sure we only
                # use named resources
                step_resources = cls._parse_resource_usage(action, declarations=resources)
                fixed_files, _variable_files = cls._parse_file_usage(action_class, action)

                step = RecipeStep(action_class, action, step_resources, fixed_files)
                steps.append(step)

            return RecipeObject(name, description, steps, resources, defaults, path)
        except RecipeFileInvalid as exc:
            cls._future_raise(RecipeFileInvalid, RecipeFileInvalid(exc.msg, recipe=name, **exc.params),
                              sys.exc_info()[2])

    @classmethod
    def _future_raise(cls, tp, value=None, tb=None):
        if value is not None and isinstance(tp, Exception):
            raise TypeError("instance exception may not have a separate value")
        if value is not None:
            exc = tp(value)
        else:
            exc = tp
        if exc.__traceback__ is not tb:
            raise exc.with_traceback(tb)
        raise exc

    @classmethod
    def _parse_file_usage(cls, action_class, args):
        """Find all external files referenced by an action."""

        fixed_files = {}
        variable_files = []

        if not hasattr(action_class, 'FILES'):
            return fixed_files, variable_files

        for file_arg in action_class.FILES:
            arg_value = args.get(file_arg)
            if arg_value is None:
                raise RecipeFileInvalid("Action lists a file argument but none was given", declared_argument=file_arg, passed_arguments=args)

            variables = _extract_variables(arg_value)
            if len(variables) == 0:
                fixed_files[file_arg] = arg_value
            else:
                variable_files.append(arg_value)

        return fixed_files, variable_files

    @classmethod
    def _parse_resource_declarations(cls, declarations, resource_map):
        """Parse out what resources are declared as shared for this recipe."""

        resources = {}

        for decl in declarations:
            name = decl.pop('name')
            typename = decl.pop('type')
            desc = decl.pop('description', None)
            autocreate = decl.pop('autocreate', False)

            args = decl

            res_type = resource_map.get(typename)
            if res_type is None:
                raise UnknownRecipeResourceType("Could not find shared resource type", type=typename, name=name)

            # If the resource defines an argument schema, make sure we enforce it.
            if hasattr(res_type, "ARG_SCHEMA"):
                try:
                    args = res_type.ARG_SCHEMA.verify(args)
                except ValidationError as exc:
                    raise RecipeFileInvalid("Recipe file resource declarttion has invalid parameters", resource=name, error_message=exc.msg, **exc.params)

            if name in resources:
                raise RecipeFileInvalid("Attempted to add two shared resources with the same name", name=name)

            res = ResourceDeclaration(name, resource_map.get(typename), args, autocreate, desc, typename)
            resources[name] = res

        return resources

    @classmethod
    def _parse_variable_defaults(cls, defaults):
        """Parse out all of the variable defaults."""

        default_dict = {}

        for item in defaults:
            key = next(iter(item))
            value = item[key]

            if key in default_dict:
                raise RecipeFileInvalid("Default variable value specified twice", name=key, old_value=default_dict[key], new_value=value)

            default_dict[key] = value

        return default_dict

    @classmethod
    def _parse_resource_usage(cls, action_dict, declarations):
        """Parse out what resources are used, opened and closed in an action step."""

        raw_used = action_dict.pop('use', [])
        opened = [x.strip() for x in action_dict.pop('open_before', [])]
        closed = [x.strip() for x in action_dict.pop('close_after', [])]

        used = {}

        for resource in raw_used:
            if 'as' in resource:
                global_name, _, local_name = resource.partition('as')
                global_name = global_name.strip()
                local_name = local_name.strip()

                if len(global_name) == 0 or len(local_name) == 0:
                    raise RecipeFileInvalid("Resource usage specified in action with invalid name using 'as' statement", global_name=global_name, local_name=local_name, statement=resource)
            else:
                global_name = resource.strip()
                local_name = global_name

            if local_name in used:
                raise RecipeFileInvalid("Resource specified twice for action", args=action_dict, resource=local_name, used_resources=used)

            used[local_name] = global_name

        # Make sure we only use, open and close declared resources
        for name in (x for x in used.values() if x not in declarations):
            raise RecipeFileInvalid("Action makes use of non-declared shared resource", name=name)

        for name in (x for x in opened if x not in declarations):
            raise RecipeFileInvalid("Action specified a non-declared shared resource in open_before", name=name)

        for name in (x for x in closed if x not in declarations):
            raise RecipeFileInvalid("Action specified a non-declared shared resource in close_after", name=name)

        return ResourceUsage(used, opened, closed)

    @classmethod
    def _process_yaml(cls, yamlfile):
        import yaml
        with open(yamlfile, 'r') as infile:
            info = yaml.load(infile)
            return info

    def prepare(self, variables):
        """Initialize all steps in this recipe using their parameters.

        Args:
            variables (dict): A dictionary of global variable definitions
                that may be used to replace or augment the parameters given
                to each step.

        Returns:
            list of RecipeActionObject like instances: The list of instantiated
                steps that can be used to execute this recipe.
        """
        initializedsteps = []
        if variables is None:
            variables = dict()
        for step, params, _resources, _files in self.steps:
            new_params = _complete_parameters(params, variables)
            initializedsteps.append(step(new_params))
        return initializedsteps

    def _prepare_resources(self, variables, overrides=None):
        """Create and optionally open all shared resources."""

        if overrides is None:
            overrides = {}

        res_map = {}
        own_map = {}

        for decl in self.resources.values():
            resource = overrides.get(decl.name)

            if resource is None:
                args = _complete_parameters(decl.args, variables)
                resource = decl.type(args)
                own_map[decl.name] = resource

            if decl.autocreate:
                resource.open()

            res_map[decl.name] = resource

        return res_map, own_map

    def _cleanup_resources(self, initialized_resources):
        """Cleanup all resources that we own that are open."""

        cleanup_errors = []

        # Make sure we clean up all resources that we can and don't error out at the
        # first one.
        for name, res in initialized_resources.items():
            try:
                if res.opened:
                    res.close()
            except Exception:
                _type, value, traceback = sys.exc_info()
                cleanup_errors.append((name, value, traceback))

        if len(cleanup_errors) > 0:
            raise RecipeResourceManagementError(operation="resource cleanup", errors=cleanup_errors)

    def run(self, variables=None, overrides=None):
        """Initialize and run this recipe.

        By default all necessary shared resources are created and destroyed in
        this function unless you pass them preinitizlied in overrides, in
        which case they are used as is.  The overrides parameter is designed
        to allow testability of iotile-ship recipes by inspecting the shared
        resources after the recipe has finished to ensure that it was properly
        set up.

        Args:
            variables (dict): An optional dictionary of variable assignments.
                There must be a single assignment for all free variables that
                do not have a default value, otherwise the recipe will not
                run.
            overrides (dict): An optional dictionary of shared resource
                objects that should be used instead of creating that resource
                and destroying it inside this function.
        """

        old_dir = os.getcwd()
        try:
            os.chdir(self.run_directory)

            initialized_steps = self.prepare(variables)
            owned_resources = {}

            try:
                print("Running in %s" % self.run_directory)
                initialized_resources, owned_resources = self._prepare_resources(variables, overrides)

                for i, (step, decl) in enumerate(zip(initialized_steps, self.steps)):
                    print("===> Step %d: %s\t Description: %s" % (i+1, self.steps[i][0].__name__, \
                        self.steps[i][1].get('description', '')))

                    runtime, out = _run_step(step, decl, initialized_resources)

                    print("======> Time Elapsed: %.2f seconds" % runtime)
                    if out is not None:
                        print(out[1])
            finally:
                self._cleanup_resources(owned_resources)
        finally:
            os.chdir(old_dir)

    def __str__(self):
        output_string = "========================================\n"
        output_string += "Recipe: \t%s\n" % (self.name)
        output_string += "Desciption: \t%s\n" % (self.description)
        output_string += "========================================\n"

        output_string += "\nRequired Variables:\n"
        for var in self.required_variables:
            output_string += "- %s\n" % var

        output_string += "\nOptional Variables: \n"
        for var in self.optional_variables:
            output_string += "- %s\n" % var

        output_string += "\nSteps:\n"
        for step in self.steps:
            output_string += "- %s\t Description: %s\n" % \
            (step[0].__name__, step[1].get('description', ''))
        return output_string


def _complete_parameters(param, variables):
    """Replace any parameters passed as {} in the yaml file with the variable names that are passed in

    Only strings, lists of strings, and dictionaries of strings can have
    replaceable values at the moment.

    """
    if isinstance(param, list):
        return [_complete_parameters(x, variables) for x in param]
    elif isinstance(param, dict):
        return {key: _complete_parameters(value, variables) for key, value in param.items()}
    elif isinstance(param, str):
        try:
            return Template(param).substitute(variables)
        except KeyError as exc:
            raise RecipeVariableNotPassed("Variable undefined in recipe", undefined_variable=exc.args[0])

    return param


def _extract_variables(param):
    """Find all template variables in args."""

    variables = set()

    if isinstance(param, list):
        variables.update(*[_extract_variables(x) for x in param])
    elif isinstance(param, dict):
        variables.update(*[_extract_variables(x) for x in param.values()])
    elif isinstance(param, str):
        for match in re.finditer(TEMPLATE_REGEX, param):
            if match.group('short_id') is not None:
                variables.add(match.group('short_id'))
            else:
                variables.add(match.group('long_id'))

    return variables


def _run_step(step_obj, step_declaration, initialized_resources):
    """Actually run a step."""

    start_time = time.time()

    # Open any resources that need to be opened before we run this step
    for res_name in step_declaration.resources.opened:
        initialized_resources[res_name].open()

    # Create a dictionary of all of the resources that are required for this step
    used_resources = {local_name: initialized_resources[global_name] for local_name, global_name in step_declaration.resources.used.items()}

    # Allow steps with no resources to not need a resources keyword parameter
    if len(used_resources) > 0:
        out = step_obj.run(resources=used_resources)
    else:
        out = step_obj.run()

    # Close any resources that need to be closed before we run this step
    for res_name in step_declaration.resources.closed:
        initialized_resources[res_name].close()

    end_time = time.time()

    return (end_time - start_time, out)
