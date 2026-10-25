# -*- coding: utf-8 -*-
"""ESP32 desktop flasher. Requires Python 3.8+ and Tkinter."""
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from core import SerialDecoder, encode_input, erase_args, flash_args, progress_of, validate_images


def terminate_process(process):
    """One-file EXEs may have a bootloader parent: cancel the full worker tree."""
    if sys.platform == 'win32' and getattr(sys, 'frozen', False):
        taskkill = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'taskkill.exe')
        try:
            result = subprocess.run([taskkill, '/PID', str(process.pid), '/T', '/F'],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 or process.poll() is not None:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        process.terminate()
    except OSError:
        pass


class App:
    def __init__(self, root):
        self.root = root
        root.title('ESP32 烧录与串口工具')
        root.geometry('980x740')
        root.minsize(820, 640)
        root.option_add('*Font', ('Microsoft YaHei UI', 10))
        self.events = queue.Queue(maxsize=2048)
        self.tx = queue.Queue(maxsize=100)
        self.serial = None
        self.serial_thread = None
        self.serial_stop = threading.Event()
        self.serial_generation = 0
        self.busy = False
        self.operation = '烧录'
        self.cancel = threading.Event()
        self.process = None
        self.rows = []
        self.reconnect = None
        self.port = tk.StringVar()
        self.baud = tk.StringVar(value='460800')
        self.chip = tk.StringVar(value='auto')
        self.mode = tk.StringVar(value='单个 bin')
        self.serial_baud = tk.StringVar(value='115200')
        self.encoding = tk.StringVar(value='utf-8')
        self.hex_rx = tk.BooleanVar()
        self.hex_tx = tk.BooleanVar()
        self.ending = tk.StringVar(value='CRLF')
        self.auto_monitor = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value='就绪 · 请选择串口和固件')
        self._build()
        self.refresh_ports()
        self.reset_rows()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(50, self.poll)

    def _build(self):
        style = ttk.Style()
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('TButton', padding=(10, 5))
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='ESP32 烧录与串口', font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        top = ttk.Frame(outer)
        top.pack(fill='x', pady=(10, 8))
        ttk.Label(top, text='串口').pack(side='left')
        self.ports = ttk.Combobox(top, textvariable=self.port, width=14)
        self.ports.pack(side='left', padx=6)
        self.refresh_btn = ttk.Button(top, text='刷新', command=self.refresh_ports)
        self.refresh_btn.pack(side='left')
        ttk.Label(top, text='芯片').pack(side='left', padx=(20, 6))
        self.chips = ttk.Combobox(top, textvariable=self.chip, state='readonly', width=12,
                                values=('auto', 'esp32', 'esp32s2', 'esp32s3', 'esp32c2', 'esp32c3', 'esp32c6', 'esp32h2'))
        self.chips.pack(side='left')
        ttk.Label(top, text='烧录波特率').pack(side='left', padx=(20, 6))
        self.bauds = ttk.Combobox(top, textvariable=self.baud, state='readonly', width=10,
                                values=('115200', '230400', '460800', '921600'))
        self.bauds.pack(side='left')
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both', expand=True)
        flash = ttk.Frame(self.tabs, padding=10)
        monitor = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(flash, text='  固件烧录  ')
        self.tabs.add(monitor, text='  串口交互  ')
        modes = ttk.Frame(flash)
        modes.pack(fill='x')
        ttk.Label(modes, text='烧录模式').pack(side='left')
        self.modes = ttk.Combobox(modes, textvariable=self.mode, state='readonly', width=24,
                                values=('单个 bin', 'ESP32 标准三文件', '自定义多文件'))
        self.modes.pack(side='left', padx=8)
        self.modes.bind('<<ComboboxSelected>>', lambda event: self.reset_rows())
        self.add_btn = ttk.Button(modes, text='添加 bin', command=self.add_row)
        self.add_btn.pack(side='right')
        ttk.Label(flash, text='地址必须以固件说明为准。三文件模式的应用默认地址为 0x100000（1 MB），可修改。',
                  wraplength=840).pack(anchor='w', pady=(8, 4))
        holder = ttk.Frame(flash)
        holder.pack(fill='x')
        self.canvas = tk.Canvas(holder, height=132, highlightthickness=0)
        scroll = ttk.Scrollbar(holder, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='x', expand=True)
        self.files_frame = ttk.Frame(self.canvas)
        window = self.canvas.create_window(0, 0, anchor='nw', window=self.files_frame)
        self.files_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(window, width=e.width))
        actions = ttk.Frame(flash)
        actions.pack(fill='x', pady=8)
        self.flash_btn = ttk.Button(actions, text='开始烧录', command=self.start_flash)
        self.flash_btn.pack(side='left')
        self.erase_btn = ttk.Button(actions, text='擦除整片 Flash', command=self.start_erase)
        self.erase_btn.pack(side='left', padx=(8, 0))
        self.cancel_btn = ttk.Button(actions, text='取消操作', command=self.cancel_flash, state='disabled')
        self.cancel_btn.pack(side='left', padx=8)
        ttk.Checkbutton(actions, text='烧录后打开串口', variable=self.auto_monitor).pack(side='left')
        ttk.Button(actions, text='保存日志', command=lambda: self.save_log(self.flash_log)).pack(side='right')
        self.progress = ttk.Progressbar(flash, maximum=100)
        self.progress.pack(fill='x', pady=(0, 6))
        self.flash_log = ScrolledText(flash, height=10, state='disabled', font=('Consolas', 10), wrap='word')
        self.flash_log.pack(fill='both', expand=True)
        bar = ttk.Frame(monitor)
        bar.pack(fill='x')
        ttk.Label(bar, text='波特率').pack(side='left')
        self.monitor_bauds = ttk.Combobox(bar, textvariable=self.serial_baud, width=9,
                                       values=('9600', '57600', '115200', '230400', '460800', '921600'))
        self.monitor_bauds.pack(side='left', padx=6)
        self.connect_btn = ttk.Button(bar, text='打开串口', command=self.toggle_serial)
        self.connect_btn.pack(side='left')
        ttk.Label(bar, text='编码').pack(side='left', padx=(12, 4))
        self.encodings = ttk.Combobox(bar, textvariable=self.encoding, width=7, state='readonly', values=('utf-8', 'gbk', 'ascii'))
        self.encodings.pack(side='left')
        ttk.Checkbutton(bar, text='HEX 显示', variable=self.hex_rx).pack(side='left', padx=8)
        ttk.Button(bar, text='清空', command=lambda: self.clear_log(self.serial_log)).pack(side='right')
        ttk.Button(bar, text='保存', command=lambda: self.save_log(self.serial_log)).pack(side='right', padx=4)
        ttk.Label(monitor, text='串口参数：8N1，无流控；打开时 DTR/RTS 保持低电平。编码在重新连接后生效。').pack(anchor='w', pady=8)
        self.serial_log = ScrolledText(monitor, state='disabled', font=('Consolas', 10), wrap='word')
        self.serial_log.pack(fill='both', expand=True)
        send = ttk.Frame(monitor)
        send.pack(fill='x', pady=(8, 0))
        self.input = ttk.Entry(send)
        self.input.pack(side='left', fill='x', expand=True)
        self.input.bind('<Return>', lambda e: self.send())
        ttk.Checkbutton(send, text='HEX 发送', variable=self.hex_tx).pack(side='left', padx=5)
        ttk.Combobox(send, textvariable=self.ending, state='readonly', width=6, values=('无', 'LF', 'CRLF', 'CR')).pack(side='left')
        self.send_btn = ttk.Button(send, text='发送', command=self.send, state='disabled')
        self.send_btn.pack(side='left', padx=(6, 0))
        ttk.Label(outer, textvariable=self.status, wraplength=900).pack(anchor='w', pady=(8, 0))

    def reset_rows(self):
        if self.busy:
            return
        for child in self.files_frame.winfo_children():
            child.destroy()
        self.rows = []
        header = ttk.Frame(self.files_frame)
        header.pack(fill='x', pady=(0, 3))
        ttk.Label(header, text='固件', width=10).pack(side='left')
        ttk.Label(header, text='烧录地址', width=12).pack(side='left', padx=(0, 6))
        ttk.Label(header, text='bin 文件路径').pack(side='left')
        if self.mode.get() == 'ESP32 标准三文件':
            self.chip.set('esp32')
            for address, name in [('0x1000', 'bootloader'), ('0x8000', '分区表'), ('0x100000', '应用')]:
                self.add_row(address, name)
        else:
            self.add_row()
        self.add_btn.configure(state='normal' if self.mode.get() == '自定义多文件' else 'disabled')

    def add_row(self, address='', name='bin'):
        if self.busy:
            return
        frame = ttk.Frame(self.files_frame)
        frame.pack(fill='x', pady=3)
        offset = tk.StringVar(value=address)
        path = tk.StringVar()
        ttk.Label(frame, text=name, width=10).pack(side='left')
        ttk.Entry(frame, textvariable=offset, width=12).pack(side='left', padx=(0, 6))
        ttk.Entry(frame, textvariable=path).pack(side='left', fill='x', expand=True)
        def browse():
            result = filedialog.askopenfilename(title='选择 bin 固件', filetypes=[('BIN 固件', '*.bin')])
            if result:
                path.set(result)
        ttk.Button(frame, text='选择文件', command=browse).pack(side='left', padx=5)
        row = (offset, path, frame)
        def remove():
            if not self.busy:
                self.rows.remove(row)
                frame.destroy()
        if self.mode.get() == '自定义多文件':
            ttk.Button(frame, text='移除', command=remove).pack(side='left')
        self.rows.append(row)

    def refresh_ports(self):
        try:
            from serial.tools import list_ports
            ports = list(list_ports.comports())
            self.ports['values'] = [p.device for p in ports]
            if not self.port.get() and ports:
                self.port.set(ports[0].device)
            self.status.set('发现 %d 个串口；也可手动输入 COM 端口。' % len(ports))
        except ImportError:
            self.status.set('缺少依赖，请先运行 install_win7.bat。')

    def emit(self, kind, value):
        # Backpressure prevents high baud rates from exhausting memory.
        while True:
            try:
                self.events.put((kind, value), timeout=0.1)
                return
            except queue.Full:
                if not self.root_alive:
                    return

    @property
    def root_alive(self):
        return not getattr(self, 'closing', False)

    def log(self, widget, text):
        widget.configure(state='normal')
        widget.insert('end', text)
        if int(widget.index('end-1c').split('.')[0]) > 4000:
            widget.delete('1.0', '1000.0')
        # Also cap a continuous stream with no newline.
        if int(widget.count('1.0', 'end', 'chars')[0]) > 300000:
            widget.delete('1.0', '1.0+100000c')
        widget.see('end')
        widget.configure(state='disabled')

    def clear_log(self, widget):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.configure(state='disabled')

    def save_log(self, widget):
        path = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('文本日志', '*.txt')])
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as output:
                    output.write(widget.get('1.0', 'end-1c'))
            except OSError as exc:
                messagebox.showerror('保存失败', str(exc))

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.flash_btn, self.erase_btn, self.refresh_btn, self.connect_btn):
            widget.configure(state='disabled' if busy else 'normal')
        self.cancel_btn.configure(state='normal' if busy else 'disabled')
        for widget in (self.modes, self.chips, self.bauds):
            widget.configure(state='disabled' if busy else 'readonly')
        self.ports.configure(state='disabled' if busy or self.serial else 'normal')
        self.add_btn.configure(state='normal' if not busy and self.mode.get() == '自定义多文件' else 'disabled')
        for _, _, frame in self.rows:
            for widget in frame.winfo_children():
                if isinstance(widget, (ttk.Entry, ttk.Button)):
                    widget.configure(state='disabled' if busy else 'normal')

    def start_flash(self):
        if self.busy:
            return
        try:
            images = validate_images([(a.get(), p.get()) for a, p, _ in self.rows])
            args = flash_args(self.port.get(), self.baud.get(), self.chip.get(), images)
            import esptool  # check before releasing the monitor
        except (ValueError, OSError, ImportError) as exc:
            messagebox.showerror('无法开始烧录', str(exc))
            return
        self.start_operation(args, '烧录')

    def start_erase(self):
        if self.busy:
            return
        try:
            args = erase_args(self.port.get(), self.baud.get(), self.chip.get())
            import esptool
        except (ValueError, ImportError) as exc:
            messagebox.showerror('无法开始擦除', str(exc))
            return
        if not messagebox.askyesno('确认擦除整片 Flash',
                '即将擦除 %s 上设备的整片 Flash。\n\n'
                '固件、分区表、NVS 配置及其他 Flash 数据都会被清除，无法恢复。'
                '\n擦除后需要重新烧录固件。\n\n是否继续？' % self.port.get(),
                icon='warning', default='no'):
            return
        self.start_operation(args, '擦除')

    def start_operation(self, args, operation):
        self.operation = operation
        self.reconnect = (self.port.get(), self.serial_baud.get(), self.encoding.get()) if self.serial else None
        self.disconnect_serial()
        self.cancel.clear()
        self.progress['value'] = 0
        self.progress.configure(mode='indeterminate' if operation == '擦除' else 'determinate')
        if operation == '擦除':
            self.progress.start(15)
        self.set_busy(True)
        self.status.set('正在%s · 请勿拔出设备' % operation)
        self.log(self.flash_log, '\n[%s] 开始%s：%s\n' % (time.strftime('%H:%M:%S'), operation, subprocess.list2cmdline(args)))
        threading.Thread(target=self.flash_worker, args=(args,), daemon=True).start()

    def flash_worker(self, args):
        code = -1
        try:
            command = ([sys.executable, '--flash-worker'] if getattr(sys, 'frozen', False)
                       else [sys.executable, '-u', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flash_worker.py')])
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUNBUFFERED'] = '1'
            self.process = subprocess.Popen(command + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            stdin=subprocess.DEVNULL, env=env,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if self.cancel.is_set():
                terminate_process(self.process)
            pending = bytearray()
            while True:
                chunk = self.process.stdout.read(1)
                if not chunk:
                    break
                if chunk in (b'\r', b'\n'):
                    if pending:
                        self.emit('flash_log', pending.decode('utf-8', errors='replace') + '\n')
                        pending.clear()
                else:
                    pending.extend(chunk)
            if pending:
                self.emit('flash_log', pending.decode('utf-8', errors='replace') + '\n')
            code = self.process.wait()
        except Exception as exc:
            self.emit('flash_log', '%s进程异常：%s\n' % (self.operation, exc))
        finally:
            if self.process:
                if self.process.poll() is None:
                    terminate_process(self.process)
                    self.process.wait()
                self.process.stdout.close()
            self.process = None
            self.emit('flash_done', (code, self.cancel.is_set()))

    def cancel_flash(self):
        self.cancel.set()
        self.cancel_btn.configure(state='disabled')
        self.status.set('正在取消%s……' % self.operation)
        process = self.process
        if process and process.poll() is None:
            terminate_process(process)

    def toggle_serial(self):
        if self.serial:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        if self.busy or self.serial:
            return
        try:
            import serial
            if not self.port.get().strip():
                raise ValueError('请选择串口。')
            baud = int(self.serial_baud.get())
            if baud <= 0:
                raise ValueError('串口波特率必须大于零。')
            device = serial.Serial(port=None, baudrate=baud, timeout=0.05, write_timeout=0.5)
            device.dtr = False
            device.rts = False
            device.port = self.port.get().strip()
            device.open()
        except Exception as exc:
            messagebox.showerror('串口打开失败', str(exc))
            return
        self.serial = device
        self.serial_stop = threading.Event()
        self.tx = queue.Queue(maxsize=100)
        self.serial_generation += 1
        self.serial_thread = threading.Thread(target=self.read_serial,
            args=(device, self.serial_stop, self.tx, self.serial_generation), daemon=True)
        self.serial_thread.start()
        self.connect_btn.configure(text='关闭串口')
        self.send_btn.configure(state='normal')
        self.ports.configure(state='disabled')
        self.monitor_bauds.configure(state='disabled')
        self.encodings.configure(state='disabled')
        self.status.set('串口已连接：%s @ %d' % (device.port, baud))
        self.log(self.serial_log, '\n[已连接 %s @ %d]\n' % (device.port, baud))

    def disconnect_serial(self):
        self.serial_generation += 1
        self.serial_stop.set()
        device, self.serial = self.serial, None
        if device:
            try:
                device.close()
            except OSError:
                pass
            if self.serial_thread:
                self.serial_thread.join(timeout=0.7)
            self.log(self.serial_log, '\n[串口已关闭]\n')
        self.connect_btn.configure(text='打开串口')
        self.send_btn.configure(state='disabled')
        self.ports.configure(state='normal')
        self.monitor_bauds.configure(state='normal')
        self.encodings.configure(state='readonly')
        self.status.set('串口已关闭')

    def read_serial(self, device, stop, tx, generation):
        try:
            while not stop.is_set():
                try:
                    data = tx.get_nowait()
                except queue.Empty:
                    data = None
                if data is not None:
                    written = device.write(data)
                    if written != len(data):
                        raise OSError('串口发送不完整，请检查连接。')
                    self.emit('serial_tx', (generation, data))
                data = device.read(min(4096, max(1, device.in_waiting)))
                if data:
                    self.emit('serial_data', (generation, data))
        except Exception as exc:
            if not stop.is_set():
                self.emit('serial_error', (generation, str(exc)))

    def send(self):
        if not self.serial:
            return
        try:
            data = encode_input(self.input.get(), self.hex_tx.get(), self.ending.get(), self.encoding.get())
            if len(data) > 16384:
                raise ValueError('单次发送不能超过 16384 字节。')
            if data:
                self.tx.put_nowait(data)
                self.input.delete(0, 'end')
        except (ValueError, UnicodeError, queue.Full) as exc:
            messagebox.showerror('发送失败', str(exc) or '发送队列已满，请稍后重试。')

    def poll(self):
        try:
            for _ in range(150):
                kind, value = self.events.get_nowait()
                if kind == 'flash_log':
                    self.log(self.flash_log, value)
                    progress = progress_of(value)
                    if progress is not None:
                        self.progress['value'] = progress
                elif kind == 'flash_done':
                    code, cancelled = value
                    self.progress.stop()
                    self.progress.configure(mode='determinate')
                    self.progress['value'] = 0
                    self.set_busy(False)
                    success = code == 0 and not cancelled
                    if self.operation == '擦除':
                        text = ('擦除已取消；Flash 可能已部分清除，请重新擦除后烧录。' if cancelled else
                                '整片 Flash 擦除完成，请重新烧录固件。' if success else
                                '擦除失败。请检查串口与连接；必要时按住 BOOT 后重试，或降低波特率。')
                    else:
                        text = ('烧录已取消；固件可能不完整，请重新烧录。' if cancelled else
                                '烧录完成，校验通过。' if success else
                                '烧录失败。请检查串口、地址与连接；必要时按住 BOOT 后重试，或降低波特率。')
                    self.status.set(text)
                    self.log(self.flash_log, text + '\n')
                    if success:
                        self.progress['value'] = 100
                    if self.reconnect or (success and self.operation == '烧录' and self.auto_monitor.get()):
                        if self.reconnect:
                            self.port.set(self.reconnect[0])
                            self.serial_baud.set(self.reconnect[1])
                            self.encoding.set(self.reconnect[2])
                        self.root.after(500, self.connect_serial)
                    self.reconnect = None
                elif kind.startswith('serial_'):
                    generation, data = value
                    if generation != self.serial_generation:
                        continue
                    if kind == 'serial_error':
                        self.disconnect_serial()
                        self.status.set('串口断开：' + data)
                        self.log(self.serial_log, '\n[串口错误] ' + data + '\n')
                    elif kind == 'serial_data':
                        mode = (generation, self.encoding.get(), self.hex_rx.get())
                        if getattr(self, '_decode_mode', None) != mode:
                            self._decode_mode = mode
                            self.decoder = SerialDecoder(self.encoding.get())
                        text = (' '.join('%02X' % b for b in data) + ' ') if mode[2] else self.decoder.decode(data)
                        self.log(self.serial_log, text)
                    elif kind == 'serial_tx':
                        self.log(self.serial_log, '\n[TX] ' + repr(data) + '\n')
        except queue.Empty:
            pass
        if self.root_alive:
            self.root.after(50, self.poll)

    def close(self):
        if self.busy and not messagebox.askyesno('退出', '正在%s。退出会中断操作，是否退出？' % self.operation):
            return
        self.closing = True
        self.cancel_flash()
        self.disconnect_serial()
        self.root.destroy()


def main():
    if '--flash-worker' in sys.argv:
        from flash_worker import main as worker
        worker(sys.argv[sys.argv.index('--flash-worker') + 1:])
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
