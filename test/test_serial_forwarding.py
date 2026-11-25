import importlib.util
import os
import socket
import time
import unittest
from unittest import mock

_path = os.path.join(os.path.dirname(__file__), '..', 'tools', 'dronecan_serial_forwarding.py')
_spec = importlib.util.spec_from_file_location('dronecan_serial_forwarding', _path)
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)


class FakeTunnel:
    def __init__(self, *args, **kwargs):
        self.closed = False

    def read(self, n):
        return b''

    def write(self, buf):
        pass

    def close(self):
        self.closed = True


def make_forwarder():
    '''serialForwarding without __init__: no CAN node, no background timers'''
    fwd = sf.serialForwarding.__new__(sf.serialForwarding)
    fwd.sock = None
    fwd.listen_sock = None
    fwd.addr = None
    fwd.tunnel = None
    fwd.num_rx_bytes = 0
    fwd.num_tx_bytes = 0
    fwd.node = None
    fwd.node_id = 10
    fwd.i = 0
    fwd.device = 'fake'
    fwd.baudrate = 115200
    fwd.target_dev = -1
    fwd.port = 0  # ephemeral port
    fwd.state = "disconnected"
    return fwd


class TestSerialForwardingEOF(unittest.TestCase):
    def test_peer_close_releases_socket_and_tunnel(self):
        local, peer = socket.socketpair()
        local.setblocking(False)
        fwd = make_forwarder()
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

    @mock.patch.object(sf.dronecan, 'DroneCANSerial', FakeTunnel)
    @mock.patch.object(sf.threading, 'Timer')
    def test_reconnect_after_clean_disconnect(self, _timer):
        fwd = make_forwarder()
        fwd.restart_listen()
        addr = ('127.0.0.1', fwd.listen_sock.getsockname()[1])
        self.addCleanup(fwd.listen_sock.close)

        client_a = socket.create_connection(addr)
        fwd.check_connection()
        self.assertIsNotNone(fwd.sock)
        tunnel_a = fwd.tunnel

        # client A disconnects normally, client B is waiting in the backlog
        client_a.close()
        client_b = socket.create_connection(addr)
        self.addCleanup(client_b.close)
        b_addr = client_b.getsockname()

        for _ in range(100):
            fwd.check_connection()
            if fwd.tunnel is not tunnel_a:
                break
            time.sleep(0.01)

        self.assertTrue(tunnel_a.closed)
        self.assertIsNotNone(fwd.sock)
        self.assertIsNotNone(fwd.tunnel)
        self.assertIsNot(fwd.tunnel, tunnel_a)
        self.assertEqual(fwd.sock.getpeername(), b_addr)
        self.assertEqual(fwd.state, "connection from %s:%u" % b_addr)
        fwd.sock.close()


if __name__ == '__main__':
    unittest.main()
