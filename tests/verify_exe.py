"""Smoke test the standalone EXE with Python removed from its search path."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    executable = Path(sys.argv[1]).resolve()
    environment = os.environ.copy()
    for key in list(environment):
        if key.upper().startswith(('PYTHON', '_PYI', '_MEIPASS')):
            environment.pop(key)
    environment['PATH'] = os.path.join(environment.get('SystemRoot', 'C:\\Windows'), 'System32')
    reports = []
    with tempfile.TemporaryDirectory(prefix='esp32-exe-') as directory:
        standalone = Path(directory) / executable.name
        shutil.copy2(str(executable), str(standalone))
        for arguments, expected in [(['version'], 0),
                                    (['--chip', 'esp32', '--port', 'COM_DOES_NOT_EXIST', 'chip_id'], 2),
                                    (['--chip', 'esp32', '--port', 'COM_DOES_NOT_EXIST', 'erase_flash'], 2)]:
            result = subprocess.run([str(standalone), '--flash-worker'] + arguments,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=environment, cwd=directory,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=45)
            output = result.stdout.decode('utf-8', errors='replace')
            assert result.returncode == expected, (result.returncode, output)
            assert '4.8.1' in output, output
            assert 'Traceback' not in output, output
            if expected:
                assert 'COM_DOES_NOT_EXIST' in output and ('open' in output.lower()), output
            reports.append({'args': arguments, 'exit_code': result.returncode, 'output': output})
    print(json.dumps({'standalone_exe': str(executable), 'tests': reports}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
