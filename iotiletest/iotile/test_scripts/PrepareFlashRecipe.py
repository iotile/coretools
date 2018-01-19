import subprocess, time, os, sys, csv
class PrepareFlashRecipe(object):
    def __init__(self, chip_name, segger_id, executive_file, application_file):
        self._chip_name = chip_name
        self._segger_id = segger_id
        self._exe_file  = executive_file
        self._app_file  = application_file
        self._gdbserver = None

    def _load_firmware(self, file):
        if self._gdbserver is not None:
            print("--> Writing tile firmware %s " % file)            
            output = subprocess.check_output(['arm-none-eabi-gdb.exe', '-q', '--batch-silent', 
                '-ex', 'file %s' % (file.replace('\\','//')),
                '-ex', 'target remote localhost:2331',
                '-ex', 'load',
                '-ex', 'monitor reset',
                '-ex', 'kill',
                '-ex', 'quit'])
            return output
        
    def _load_exec_and_app(self):
        with open(os.devnull, 'w') as f:
            output1 = self._load_firmware(self._exe_file)
            output2 = self._load_firmware(self._app_file)

    def _open_gdb_server(self):
        print("--> Opening GDB Server")
        
        gdbserver_path = 'C:\Program Files (x86)\SEGGER\JLink_V612a\JLinkGDBServerCL.exe'
        nrfargs = '-select USB=%s -device %s -if SWD -speed auto -noir' % (self._segger_id, self._chip_name)
        self._gdbserver = subprocess.Popen('"' + gdbserver_path + '" ' + nrfargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)
        connected = self._gdbserver.poll()
        if(connected is None):
            return True
        else:
            err =  self._gdbserver.stderr.read()
            if ("Failed to open listener port 2331" not in err):
                print err
                self._gdbserver.terminate()
                self._gdbserver = None
                return False
            else:
                return True

    def _close_gdb_server(self):
        if self._gdbserver is not None:
            print("--> Closing GDB Server")
            self._gdbserver.terminate()
        
    def load(self):
        if(self._open_gdb_server()):
            self._load_exec_and_app()
            self._close_gdb_server()
            return True
        else:
            return False