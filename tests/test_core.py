import os
import tempfile
import unittest

from core import SerialDecoder, encode_input, flash_args, progress_of, validate_images


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, '中文 firmware.bin')
        with open(self.path, 'wb') as f:
            f.write(b'\xe9' * 4097)

    def tearDown(self):
        self.temp.cleanup()

    def test_address_and_unicode_path(self):
        self.assertEqual(validate_images([('0x1000', self.path)]), [(4096, self.path)])
        self.assertEqual(validate_images([('65536', self.path)]), [(65536, self.path)])

    def test_reject_unsafe_ranges(self):
        for address in ('', '-1', '1', 'xyz', '0x1000000'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                validate_images([(address, self.path)])
        with self.assertRaises(ValueError):
            validate_images([('0x0', self.path), ('0x1000', self.path)])
        self.assertEqual(len(validate_images([('0x2000', self.path), ('0x0', self.path)])), 2)

    def test_missing_and_empty(self):
        with self.assertRaises(ValueError):
            validate_images([])
        with self.assertRaises(ValueError):
            validate_images([('0x0', self.path + '.missing')])
        with open(self.path, 'wb'):
            pass
        with self.assertRaises(ValueError):
            validate_images([('0x0', self.path)])

    def test_command_keeps_path_as_one_argument(self):
        args = flash_args('COM12', '115200', 'esp32', [(4096, self.path)])
        self.assertEqual(args[-2:], ['0x1000', self.path])
        self.assertIn('write_flash', args)
        self.assertNotIn('--force', args)
        with self.assertRaises(ValueError):
            flash_args('', '115200', 'auto', [])

    def test_serial_encoding_and_hex(self):
        self.assertEqual(encode_input('你好', False, 'CRLF', 'gbk'), '你好\r\n'.encode('gbk'))
        self.assertEqual(encode_input('01 02 FF', True, 'CRLF', 'utf-8'), b'\x01\x02\xff')
        with self.assertRaises(ValueError):
            encode_input('GG', True, '无', 'utf-8')
        decoder = SerialDecoder()
        data = '中'.encode('utf-8')
        self.assertEqual(decoder.decode(data[:1]), '')
        self.assertEqual(decoder.decode(data[1:]), '中')

    def test_progress(self):
        self.assertEqual(progress_of('Writing at 0x0000... ( 37 %)'), 37)
        self.assertIsNone(progress_of('Connecting...'))


if __name__ == '__main__':
    unittest.main()
