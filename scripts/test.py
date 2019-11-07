import os
import time
import subprocess
import sys
import cmdln
import components

from subprocess import Popen, PIPE, STDOUT
from time import sleep, monotonic

def checkOutput(cmd):
    a = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    print(a.pid)
    start = monotonic()
    while a.poll() == None or monotonic()-start <= 30: #30 sec grace period
        sleep(0.25)
    if a.poll() == None:
        print('Still running, killing')
        a.kill()
    else:
        print('exit code:',a.poll())
    output = a.stdout.read()
    a.stdout.close()
    a.stdin.close()
    return output

def run_test(component, args):
    comp = components.comp_names[component]

    currdir = os.getcwd()

    testcmd = ['pytest'] + list(args) + ['-s']
    output_status = 0

    if sys.version_info.major >= 3 and not comp.py3k_clean:
        return None, ""
    elif sys.version_info.major == 2 and not comp.py2k_clean:
        return None, ""

    try:
        os.chdir(comp.path)

        with open(os.devnull, "wb") as devnull:
            try:
                output = subprocess.check_output(testcmd, stderr=subprocess.STDOUT, timeout=60)
            except subprocess.TimeoutExpired as exc:
                print("test timeout, command was: ", exc.cmd)
                print("Here is some potential test output: ", exc.output.decode("utf-8"))
                output = exc.output
                output_status = 1

    except subprocess.CalledProcessError as exc:
        output_status = exc.returncode
        output = exc.output
    except Exception as exc:  # pylint:disable=broad-except; We want some output first
        output = str(exc)
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
            if comp_name != 'iotile_transport_bled112':
                continue
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
