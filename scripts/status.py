"""Check whether there are changes since the last released version of a component
"""
import subprocess
import cmdln
import sys
import components

def get_tags():
    data = subprocess.check_output(['git', '--no-pager', 'tag'])

    tags = data.split('\n')
    tags = [x for x in tags if len(x) > 0]

    releases = [(x.partition('-')[0], x.partition('-')[2]) for x in tags]
    return releases

def get_released_versions(component):
    """Get all released versions of the given component ordered newest to oldest
    """

    releases = get_tags()

    releases = sorted([(x[0], map(int, x[1].split('.'))) for x in releases], key=lambda x: x[1])[::-1]

    return [(x[0], ".".join(map(str, x[1]))) for x in releases if x[0] == component]

def get_changed_since_tag(tag, filter_dir):
    data = subprocess.check_output(['git', '--no-pager', 'diff', '--name-only', tag, '--', filter_dir])
    return data.strip()

class StatusProcessor(cmdln.Cmdln):
    name = 'status'

    def do_releases(self, subcmd, opts, component):
        """${cmd_name}: print all releases for the given component

        ${cmd_usage}
        ${cmd_option_list}
        """

        releases = get_released_versions(component)
        for x in releases:
            print("{} - {}".format(*x))

    def do_latest(self, subcmd, opts, component):
        """${cmd_name}: print the latest release version of a given component

        ${cmd_usage}
        ${cmd_option_list}
        """

        releases = get_released_versions(component)
        if len(releases) == 0:
            print("NOT RELEASED")
            return 1
        else:
            print(releases[0][1])
            return 0

    def do_dirty(self, subcmd, opts):
        """${cmd_name}: check if any components have unreleased changes

        ${cmd_usage}
        ${cmd_option_list}
        """

        for comp_name, comp_parts in components.comp_names.iteritems():
            releases = get_released_versions(comp_name)
            if len(releases) == 0:
                print(comp_name + ' - ' + 'No tagged releases')
            else:
                latest_tag = '-'.join(releases[0])
                data = get_changed_since_tag(latest_tag, comp_parts[1])
                if len(data) > 0:
                    print(comp_name + ' - ' + 'Changed files in component tree')

    def do_changed(self, subcmd, opts, component):
        """${cmd_name}: print all files changes in component since the latest release

        ${cmd_usage}
        ${cmd_option_list}
        """

        releases = get_released_versions(component)
        latest = releases[0]

        filter_dir = components.comp_names[component][1]

        latest_tag = '-'.join(latest)
        data = get_changed_since_tag(latest_tag, filter_dir)

        if len(data) > 0:
            print(data)


if __name__ == '__main__':
    proc = StatusProcessor()
    sys.exit(proc.main())
