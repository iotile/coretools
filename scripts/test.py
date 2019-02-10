from __future__ import unicode_literals, print_function, absolute_import
import os
import time
import subprocess
import sys
import cmdln
import components


def run_test(component, args):
    comp = components.comp_names[component]

    currdir = os.getcwd()

    testcmd = ['pytest'] + list(args)
    output_status = 0

    if sys.version_info.major >= 3 and not comp.py3k_clean:
        return None, ""
    elif sys.version_info.major == 2 and not comp.py2k_clean:
        return None, ""

    try:
        os.chdir(comp.path)

        with open(os.devnull, "wb") as devnull:
                output = subprocess.check_output(testcmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        output_status = exc.returncode
        output = exc.output
    finally:
        os.chdir(currdir)

    return output_status, output


class TestProcessor(cmdln.Cmdln):
    name = 'status'

    def do_test(self, subcmd, opts, component, *args):
        """${cmd_name}: run tests for component

        ${cmd_usage}
        ${cmd_option_list}
        """

        output_status, output = run_test(component, args)
        if output_status:
            sys.stdout.write(output.decode('utf-8'))
            sys.stdout.flush()

        return output_status

    def do_test_all(self, subcmd, opts, *args):
        failed = False
        failed_outputs = []

        for comp_name in sorted(components.comp_names):
            start = time.time()
            sys.stdout.write("Testing {}: ".format(comp_name))
            sys.stdout.flush()
            status, output = run_test(comp_name, args)
            end = time.time()

            duration = end - start

            if status is None:
                print("SKIPPED ON UNSUPPORTED PYTHON INTERPRETER")
            elif status == 5:
                print("NO TESTS RAN (%.1f seconds)" % duration)
            elif status != 0:
                failed = True
                failed_outputs.append(output)
                print("FAILED (%.1f seconds)" % duration)
            else:
                print("PASSED (%.1f seconds)" % duration)

        if len(failed_outputs) > 0:
            print("----------------------- ERROR LOG STARTS ------------------")

            for output in failed_outputs:
                sys.stdout.write(output.decode('utf-8'))
                sys.stdout.flush()

            print("----------------------- ERROR LOG ENDS --------------------")

        return int(failed)


if __name__ == '__main__':
    proc = TestProcessor()
    sys.exit(proc.main())
