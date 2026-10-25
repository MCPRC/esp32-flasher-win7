# ESP32 烧录与串口工具

Python + Tkinter 中文桌面程序，面向 Windows 7 SP1（32/64 位）准备。支持单个 bin、经典 ESP32 标准三文件、自定义多文件烧录，以及串口文本/HEX 收发。

## 下载

- [最新版本与免安装 EXE](https://github.com/MCPRC/esp32-flasher-win7/releases/latest)：下载 `ESP32_Flasher_Win7_EXE.zip`，解压后双击 EXE。
- 同一发布页提供 `ESP32_Flasher_Win7.zip`，包含源码及 Python 3.8 的 32/64 位离线依赖。
- [源码仓库](https://github.com/MCPRC/esp32-flasher-win7)

功能包括整片 Flash 擦除、三种烧录模式、串口文本/HEX 交互、日志保存和取消操作。三文件模式应用默认地址为 `0x100000`（1 MB），必须与固件分区表匹配。

## 免 Python EXE 版本（优先使用）

打开 `dist/ESP32_Flasher_Win7.exe` 即可使用，或解压 `ESP32_Flasher_Win7_EXE.zip` 后双击其中的同名 EXE。目标电脑**无需安装 Python、pip 或本项目依赖**。EXE 内置官方 Python 3.8.10 x86、Tk 和固定版本烧录依赖，使用 PyInstaller 5.13.2 打包，32 位程序可在 32/64 位 Windows 使用。

仍需要 Windows 7 SP1 与可用的 USB 串口驱动；系统缺失通用 C 运行库时需补齐微软系统组件。首次启动单文件 EXE 会解压到用户临时目录，稍等几秒即可。不需要把源码或 wheelhouse 与 EXE 放在一起。

开发者重建：在已安装官方 Python 3.8.10 x86 和 Windows SDK 的 Windows 上运行 `build_exe.bat "完整路径\python.exe"`。`win7.spec` 使用 SDK 的 x86 UCRT 可再发行 DLL，避免携带构建系统的系统 DLL；其他 SDK 路径可用 `UCRT_REDIST` 环境变量指定。用户使用成品 EXE 无需执行该脚本。

## 在 Windows 7 上启动

1. 使用 Windows 7 **SP1**，安装对应 USB 串口芯片的 Win7 驱动（常见 CH340、CP210x、FTDI）。在设备管理器确认 COM 端口无错误。
2. 安装 [Python 3.8.10 官方安装包](https://www.python.org/downloads/release/python-3810/)，保留 Tcl/Tk、pip、venv 组件并勾选加入 PATH。32 位 Win7 用 x86，64 位可用 x86 或 x64，Python 与离线依赖架构需一致。Python 3.9 及以上不适合作为本项目的 Win7 运行环境。
3. 双击 `install_win7.bat` 安装固定版本依赖。若找不到 Python，在命令提示符中执行：

   ```bat
   install_win7.bat "C:\Python38\python.exe"
   ```

4. 双击 `start_win7.bat`。也可使用 `.venv\Scripts\python.exe app.py`。

如果 Python 安装器提示缺少系统组件，请按安装器提示补齐 Win7 更新和 Universal C Runtime（常见为 KB2999226）；使用微软官方更新来源。串口驱动必须支持目标系统及其签名要求。

## 多模式烧录

- **单个 bin**：选择固件文件并填写地址。合并镜像常用 `0x0`；单独的应用镜像常用 `0x10000`，但必须以发布者说明为准。单独应用需要板上已有匹配的 bootloader 和分区表。
- **ESP32 标准三文件**：默认地址为 bootloader `0x1000`、分区表 `0x8000`、应用 `0x100000`（1 MB，按本项目用户要求设置），全部可编辑。分区表中的应用分区起始地址也须匹配 `0x100000`。切换到该模式会选中 `esp32` 芯片。**ESP32-S3/C3 等不要直接套用此模板**，请用自定义模式并参照编译产物的 flash_args。
- **自定义多文件**：添加/移除任意多个 bin 并填写各自地址，支持 `0x` 十六进制或十进制。切换模式会清空当前文件列表。

连接开发板，选择串口、芯片（可自动识别）、烧录波特率，点击“开始烧录”。默认保留镜像中的 Flash 模式/频率/大小，不进行整片擦除；写入涉及的扇区仍会被擦除。工具拒绝空文件、未填写地址、未对齐地址和扇区范围重叠。此版本最大支持 16 MiB 地址范围；文件内部的正确芯片、容量和安全状态由 esptool 检查，不使用强制跳过安全检查的参数。

### 擦除整片 Flash

选择串口和芯片后点击“擦除整片 Flash”，无需选择 bin 或填写地址。确认窗口会显示目标串口，默认不执行；确认后使用 esptool 的 `erase_flash` 清除固件、分区表、NVS 等整片 Flash 数据（不修改 eFuse）。数据无法恢复，完成后需重新烧录固件。工具不使用 `--force` 绕过芯片安全检查。

擦除期间显示活动进度条和实时日志，支持“取消操作”。取消或失败后 Flash 可能已部分擦除，应重新擦除后烧录。操作前自动释放串口，结束后恢复原有串口连接；擦除不会主动新增串口连接。

进度显示的是 esptool 当前文件进度，多文件时会从头计数。完成由 esptool 退出码和校验结果决定。取消会终止进程，固件可能不完整，应重新烧录。

无法连接时：先关闭其他占用串口的软件；尝试 115200；按住 BOOT，短按 EN/RESET，开始连接后松开 BOOT。需要手动进入下载模式的板子无法仅靠软件保证自动进入。

## 串口交互

在“串口交互”页打开串口，支持独立波特率、UTF-8/GBK/ASCII、HEX 显示、文本和 HEX 发送以及 LF/CRLF/CR 行尾。HEX 发送不额外追加行尾，例如 `01 02 FF`。回车发送，发送成功显示 `[TX]`，接收内容按字节流显示。UTF-8 跨串口数据块的字符会正确合并。

固定 8N1，无流控，DTR/RTS 在打开前设为低电平（具体开发板仍可能受驱动行为影响）。更改编码需重新连接。烧录自动关闭串口，结束后恢复原有连接；没有原连接时，“完成后打开串口”仅在烧录成功后生效。

后台线程处理读写与烧录，界面可持续响应。显示内容限制为约 30 万字符/4000 行以内；“保存”仅保存当前保留内容，长时间采集请及时保存。

## 离线安装

Release 的 `ESP32_Flasher_Win7.zip` 已包含 Python 3.8 对应的 **x86 和 x64 离线依赖**（`wheelhouse`），可直接在已安装 Python 3.8.10 的 Win7 上运行 `install_win7.bat`，无需联网。Git 源码仓库不包含离线依赖。离线电脑仍需事先安装 Python 和串口驱动。不要复制其他电脑的 `.venv`。

若需重新准备依赖：在联网 Windows 电脑安装与目标机同架构的 Python 3.8.10，执行 `prepare_offline.bat`，再复制完整目录到 Win7。

依赖锁定 esptool 4.8.1、pyserial 3.5，以及 cryptography 40.0.2 等兼容旧系统的版本。不能只锁 esptool 再任由其余依赖升级：cryptography 42 系列在 Win7 上有 [DLL 加载问题报告](https://github.com/pyca/cryptography/issues/10944)。烧录命令依据 [esptool v4 官方文档](https://docs.espressif.com/projects/esptool/en/release-v4/esp32/esptool/basic-commands.html)。

## 开发验证与范围

运行 `python -m unittest discover -s tests -v`，覆盖地址/扇区校验、中文路径、命令参数、串口编码和模拟烧录流程。源码使用 Python 3.8 语法，不依赖 Qt、浏览器或现代 Windows API。

已使用真实 Python 3.8.10 x86 运行软件测试，并对独立 EXE 做脱离源码目录、移除 Python 搜索路径后的子进程测试。当前环境没有 Win7 实机及 ESP32 硬件。**因此交付不能视为已经完成 Win7 实机、驱动和实际写入验收。** 实机验收：在 Win7 SP1 启动界面；分别烧录已知可用的单文件及多文件固件；验证复位启动；验证中文串口收发、拔插恢复、取消后重新烧录。不能声称对任意未更新的 Win7 或任意板卡保证直接运行。

## 许可证

本项目按 GPL-2.0-or-later 发布，与使用的 esptool 许可证保持兼容。许可证全文见 [LICENSE](LICENSE)。第三方组件保留各自许可证，详见 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES)。
