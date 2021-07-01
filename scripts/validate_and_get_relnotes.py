"""Validates that module version matches one in release and extracts release's changelog."""
import json
import os
import re
import sys

RELNOTES = "RELEASE.md"


def _get_module_version(module):
    with open(os.path.join(module, "version.py"), "r") as f:
        tmp_dict = {}
        exec(f.read(), tmp_dict)
        return tmp_dict["version"]


def _get_relnotes(module, version):
    path = os.path.join(module, RELNOTES)
    with open(path, "r") as f:
        output = []
        version_regex = r"##\s*[vV]?" + version.replace(".", r"\.")
        found = False
        for line in f:
            if not found:
                if re.match(version_regex, line):
                    found = True
                continue
            if line.startswith("##"):
                break
            stripped = line.rstrip()
            if stripped:
                output.append(stripped)
    error = ""
    if not found:
        error = f"Release notes for version `{version}` not found in `{path}`!"
    if not output:
        error = f"Release notes for version `{version}` exist in `{path}`, but are empty!"

    return error, r"\n".join(output)


def _main():
    event = json.loads(os.environ["EVENT"])

    try:
        tag = event["release"]["tag_name"]
    except KeyError:
        print("VALIDATION_NOTES=Invalid github event payload, see logs.")
        sys.stderr.write(json.dumps(event, indent=2))
        return 1

    module, version = tag.rsplit("-", 1)

    version_from_file = _get_module_version(module)
    if version_from_file != version:
        print(f"VALIDATION_NOTES=Version mismatch. Expecting `{version}`, got `{version_from_file}` from version.py")
        return 1

    error, release_notes = _get_relnotes(module, version)
    if error:
        print(f"VALIDATION_NOTES={error}")
        return 1

    print(f"VALIDATION_NOTES={release_notes}")
    return 0


if __name__ == '__main__':
    sys.exit(_main())
