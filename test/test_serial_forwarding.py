import importlib.util
import os
import socket
import unittest

_path = os.path.join(os.path.dirname(__file__), '..', 'tools', 'dronecan_serial_forwarding.py')
_spec = importlib.util.spec_from_file_location('dronecan_serial_forwarding', _path)
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)


class FakeTunnel:
    def __init__(self):
        self.closed = False

    def write(self, buf):
        pass

    def close(self):
        self.closed = True


class TestSerialForwardingEOF(unittest.TestCase):
    def test_peer_close_releases_socket_and_tunnel(self):
        local, peer = socket.socketpair()
        local.setblocking(False)
        fwd = sf.serialForwarding.__new__(sf.serialForwarding)  # skip __init__: no CAN node, no timers
        tunnel = FakeTunnel()
        fwd.sock = local
        fwd.tunnel = tunnel
        fwd.state = "connection from local peer"

        peer.close()
        fwd.process_socket()

        self.assertIsNone(fwd.sock)
        self.assertIsNone(fwd.tunnel)
        self.assertTrue(tunnel.closed)
        self.assertEqual(fwd.state, "disconnected")


if __name__ == '__main__':
    unittest.main()
