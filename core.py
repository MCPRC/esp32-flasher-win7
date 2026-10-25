"""Hardware-independent validation and command building. Python 3.8 compatible."""
import codecs
import os
import re


def validate_images(rows):
    if not rows:
        raise ValueError('请先添加至少一个 bin 文件。')
    images = []
    for address, path in rows:
        try:
            address = address.strip()
            if not address:
                raise ValueError()
            offset = int(address, 16) if address.lower().startswith('0x') else int(address, 10)
        except ValueError:
            raise ValueError('请填写有效地址，例如 0x0、0x1000 或 0x10000（以固件说明为准）。')
        if offset < 0 or offset % 4096:
            raise ValueError('烧录地址必须非负且按 0x1000（4096 字节）对齐。')
        if not os.path.isfile(path) or not path.lower().endswith('.bin'):
            raise ValueError('bin 文件不存在：' + path)
        size = os.path.getsize(path)
        if not size:
            raise ValueError('不能烧录空文件：' + path)
        end = offset + size
        if end > 0x1000000:
            raise ValueError('文件地址超出此工具支持的 16 MiB Flash 范围。')
        # Erasure occurs at sector granularity, so check padded ranges.
        images.append((offset, path, (end + 4095) // 4096 * 4096))
    images.sort()
    for previous, current in zip(images, images[1:]):
        if previous[2] > current[0]:
            raise ValueError('文件的烧录/擦除范围重叠，请检查地址。')
    return [(offset, path) for offset, path, _ in images]


def flash_args(port, baud, chip, images):
    if not port.strip():
        raise ValueError('请选择串口。')
    args = ['--chip', chip, '--port', port, '--baud', str(int(baud)),
            '--before', 'default_reset', '--after', 'hard_reset',
            'write_flash', '--flash_mode', 'keep', '--flash_freq', 'keep',
            '--flash_size', 'keep']
    for offset, path in images:
        args.extend([hex(offset), path])
    return args


def erase_args(port, baud, chip):
    if not port.strip():
        raise ValueError('请选择串口。')
    return ['--chip', chip, '--port', port.strip(), '--baud', str(int(baud)),
            '--before', 'default_reset', '--after', 'hard_reset', 'erase_flash']


def encode_input(value, hex_mode, ending, encoding):
    if hex_mode:
        try:
            return bytes.fromhex(value)
        except ValueError:
            raise ValueError('HEX 输入应为十六进制字节，例如 01 02 FF。')
    suffix = {'无': '', 'LF': '\n', 'CRLF': '\r\n', 'CR': '\r'}[ending]
    return (value + suffix).encode(encoding)


class SerialDecoder:
    def __init__(self, encoding='utf-8'):
        self.decoder = codecs.getincrementaldecoder(encoding)(errors='replace')

    def decode(self, data):
        return self.decoder.decode(data)


def progress_of(line):
    match = re.search(r'\(\s*(\d+)\s*%\)', line)
    return int(match.group(1)) if match else None
