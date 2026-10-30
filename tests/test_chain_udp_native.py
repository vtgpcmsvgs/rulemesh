"""Optional native regression: TCP-only regional exits must not leak UDP to DIRECT."""
from pathlib import Path
import os
import socket
import struct
import subprocess
import tempfile
import time
import unittest

import yaml


CORE = os.environ.get('RULEMESH_TEST_MIHOMO', '')


@unittest.skipUnless(CORE and Path(CORE).is_file(), 'Set RULEMESH_TEST_MIHOMO to a verified native Mihomo CLI')
class NativeUdpContainmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Some host network filters block even Python-to-itself loopback. Distinguish
        # that environmental limit from a core regression; never call it a pass.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            try:
                with socket.create_connection(listener.getsockname(), timeout=2):
                    pass
            except OSError as error:
                raise unittest.SkipTest('Host blocks loopback TCP; native UDP behavior unverified') from error

    def test_singleton_load_balance_contains_udp_while_selector_skips_rule(self):
        # Loopback-only positive control proves silence is caused by containment,
        # not a broken SOCKS client. No subscriptions, real credentials, TUN or DNS.
        def arrives(group_type):
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            with tempfile.TemporaryDirectory(prefix='rulemesh-native-udp-') as task:
                config = {'mixed-port': port, 'allow-lan': False, 'log-level': 'info',
                          'ipv6': False, 'mode': 'rule',
                          'proxies': [{'name': 'leaf', 'type': 'socks5', 'server': '127.0.0.1',
                                       'port': 9, 'udp': False}],
                          'proxy-groups': [{'name': 'regional', 'type': group_type, 'proxies': ['leaf']}],
                          'rules': ['MATCH,regional']}
                if group_type == 'load-balance':
                    config['proxy-groups'][0]['strategy'] = 'consistent-hashing'
                filename = Path(task) / 'config.yaml'
                filename.write_text(yaml.safe_dump(config), encoding='utf-8')
                process = subprocess.Popen([CORE, '-d', task, '-f', str(filename)],
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                control = None
                last_connect_error = None
                try:
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            self.fail('Native core exited before listening')
                        try:
                            control = socket.create_connection(('127.0.0.1', port), timeout=0.2)
                            break
                        except OSError as error:
                            last_connect_error = str(error)
                            time.sleep(0.05)
                    if control is None:
                        process.terminate()
                        output, _ = process.communicate(timeout=5)
                        self.fail('Native fixture connection failed: ' + str(last_connect_error) + '\n' + output.decode('utf-8', 'replace')[-1500:])
                    control.settimeout(2)
                    control.sendall(b'\x05\x01\x00')
                    self.assertEqual(control.recv(2), b'\x05\x00')
                    control.sendall(b'\x05\x03\x00\x01' + b'\x00' * 6)
                    response = control.recv(64)
                    self.assertEqual(response[:4], b'\x05\x00\x00\x01')
                    relay_port = struct.unpack('!H', response[8:10])[0]
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as target, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                        target.bind(('127.0.0.1', 0))
                        target.settimeout(1)
                        payload = b'rulemesh-udp-containment'
                        packet = b'\x00\x00\x00\x01' + socket.inet_aton('127.0.0.1') + struct.pack('!H', target.getsockname()[1]) + payload
                        sender.sendto(packet, ('127.0.0.1', relay_port))
                        try:
                            received, _ = target.recvfrom(4096)
                            return received == payload
                        except socket.timeout:
                            return False
                finally:
                    if control is not None:
                        control.close()
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    process.stdout.close()

        self.assertTrue(arrives('select'), 'Positive control must reproduce DIRECT fallback')
        self.assertFalse(arrives('load-balance'), 'Regional UDP must fail without DIRECT fallback')
