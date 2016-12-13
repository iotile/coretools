import os
import time
import subprocess
import sys
import cmdln
import components


def run_test(component, args, silent=False):
    distribution, subdir = components.comp_names[component]

    currdir = os.getcwd()

    testcmd = ['tox', '--'] + list(args)
    output_status = 0

    try:
        os.chdir(subdir)

        with open(os.devnull, "wb") as devnull:
            if not silent:
                output_status = subprocess.check_call(testcmd)
            else:
                output_status = subprocess.check_call(testcmd, stdout=devnull, stderr=devnull)
    except subprocess.CalledProcessError as exc:
        print("ERROR: {}\n------------------------------------\n".format(exc.returncode))
        output_status = exc.returncode
    finally:
        os.chdir(currdir)

    return output_status

class TestProcessor(cmdln.Cmdln):
    name = 'status'

    def do_test(self, subcmd, opts, component, *args):
        """${cmd_name}: run tests for component
        
        ${cmd_usage}
        ${cmd_option_list}
        """

        return run_test(component, args)

    def do_test_all(self, subcmd, opts, *args):
        failed = False
        for comp_name in components.comp_names.iterkeys():
            start = time.time()
            sys.stdout.write("Testing {}: ".format(comp_name))
            sys.stdout.flush()
            status = run_test(comp_name, args, silent=True)
            end = time.time()

            duration = end - start

            if status != 0:
                failed = True
                print("FAILED (%.1f seconds)" % duration)
            else:
                print("PASSED (%.1f seconds)" % duration)

        return int(failed)

if __name__ == '__main__':
    proc = TestProcessor()
    sys.exit(proc.main())