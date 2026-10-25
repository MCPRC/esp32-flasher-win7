import ast
import io
import os
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from app import App


class AppTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root)
        self.root.update_idletasks()

    def tearDown(self):
        self.app.closing = True
        self.app.disconnect_serial()
        for callback in self.root.tk.call('after', 'info'):
            self.root.after_cancel(callback)
        self.root.destroy()

    def test_modes_and_size(self):
        for mode, expected in [('单个 bin', 1), ('ESP32 标准三文件', 3), ('自定义多文件', 1)]:
            self.app.mode.set(mode)
            self.app.reset_rows()
            self.assertEqual(len(self.app.rows), expected)
        self.app.add_row()
        self.assertEqual(len(self.app.rows), 2)
        self.root.deiconify()
        self.root.geometry('820x640')
        self.app.tabs.select(1)
        self.root.update()
        self.assertLess(self.app.send_btn.winfo_rootx() + self.app.send_btn.winfo_width(),
                        self.root.winfo_rootx() + self.root.winfo_width() + 1)

    def test_flash_process_success_and_failure(self):
        for returncode in (0, 2):
            process = unittest.mock.Mock()
            process.stdout = io.BytesIO(b'Writing at 0x00001000... (100 %)\r\nHash of data verified.\n')
            process.wait.return_value = returncode
            process.poll.return_value = returncode
            with patch('app.subprocess.Popen', return_value=process) as launch:
                self.app.set_busy(True)
                self.app.auto_monitor.set(False)
                self.app.flash_worker(['--port', 'COM9', 'write_flash', '0x0', 'a.bin'])
                self.app.poll()
                self.assertFalse(self.app.busy)
                self.assertIn('完成' if returncode == 0 else '失败', self.app.status.get())
                self.assertFalse(launch.call_args.kwargs.get('shell', False))

    def test_cancel_before_process_launch(self):
        process = unittest.mock.Mock()
        process.stdout = io.BytesIO(b'')
        process.wait.return_value = 1
        process.poll.return_value = 1
        self.app.cancel.set()
        self.app.auto_monitor.set(False)
        with patch('app.subprocess.Popen', return_value=process):
            self.app.flash_worker([])
        process.terminate.assert_called_once()
        self.app.poll()
        self.assertIn('取消', self.app.status.get())

    def test_real_serial_loopback(self):
        import serial
        device = serial.serial_for_url('loop://', timeout=0.05, write_timeout=0.5)
        stop = threading.Event()
        self.app.serial_generation = 7
        self.app.tx.put('中文\r\n'.encode('utf-8'))
        thread = threading.Thread(target=self.app.read_serial, args=(device, stop, self.app.tx, 7), daemon=True)
        thread.start()
        try:
            time.sleep(0.2)
            self.app.poll()
            self.assertIn('中文', self.app.serial_log.get('1.0', 'end'))
        finally:
            stop.set()
            thread.join(1)
            device.close()

    def test_stale_serial_event_ignored(self):
        self.app.emit('serial_error', (-1, 'old disconnect'))
        self.app.poll()
        self.assertNotIn('old disconnect', self.app.status.get())

    def test_erase_confirmation_declined_has_no_effect(self):
        self.app.port.set('COM9')
        with patch('app.messagebox.askyesno', return_value=False), patch.object(self.app, 'start_operation') as start:
            self.app.start_erase()
        start.assert_not_called()
        self.assertFalse(self.app.busy)

    def test_erase_needs_port_but_no_bin(self):
        with patch('app.messagebox.showerror') as error, patch('app.messagebox.askyesno') as confirm:
            self.app.port.set('')
            self.app.start_erase()
            error.assert_called_once()
            confirm.assert_not_called()
        self.app.port.set('COM9')
        with patch('app.messagebox.askyesno', return_value=True), patch.object(self.app, 'start_operation') as start:
            self.app.start_erase()
        arguments, operation = start.call_args.args
        self.assertEqual(operation, '擦除')
        self.assertEqual(arguments[-1], 'erase_flash')
        self.assertNotIn('--force', arguments)

    def test_erase_completion_failure_and_cancel(self):
        self.app.operation = '擦除'
        for code, cancelled, expected in [(0, False, '擦除完成'), (2, False, '擦除失败'), (0, True, '擦除已取消')]:
            with self.subTest(code=code, cancelled=cancelled), patch.object(self.root, 'after') as after:
                self.app.set_busy(True)
                self.app.emit('flash_done', (code, cancelled))
                self.app.poll()
                self.assertIn(expected, self.app.status.get())
                self.assertFalse(self.app.busy)
                self.assertEqual(str(self.app.erase_btn['state']), 'normal')
                self.assertFalse(any(call.args[0] == 500 for call in after.call_args_list))

    def test_erase_uses_background_worker(self):
        self.app.port.set('COM9')
        with patch('app.messagebox.askyesno', return_value=True), patch('app.threading.Thread') as worker:
            self.app.start_erase()
        self.assertTrue(self.app.busy)
        self.assertEqual(str(self.app.progress['mode']), 'indeterminate')
        self.assertEqual(str(self.app.flash_btn['state']), 'disabled')
        self.assertEqual(str(self.app.erase_btn['state']), 'disabled')
        self.assertEqual(worker.call_args.kwargs['args'][0][-1], 'erase_flash')
        worker.return_value.start.assert_called_once()
        self.app.progress.stop()

    def test_python38_syntax(self):
        for name in ('app.py', 'core.py', 'flash_worker.py'):
            with open(name, encoding='utf-8') as f:
                ast.parse(f.read(), feature_version=(3, 8))


if __name__ == '__main__':
    unittest.main()
