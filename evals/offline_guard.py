"""Pytest plugin: block sockets even during collection; HTTP mocks still work."""
import socket
import ipaddress


def blocked(*args, **kwargs):
    raise AssertionError('Offline evaluation attempted network access')


def pytest_addoption(parser):
    parser.addoption('--eval-allow-loopback', action='store_true', help='Permit local WebSocket integration tests only')


def pytest_configure(config):
    if config.getoption('--eval-allow-loopback'):
        connect, connect_ex, resolve = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo
        def local(host):
            if host == 'localhost':
                return True
            try:
                return ipaddress.ip_address(host).is_loopback
            except (ValueError, TypeError):
                return False
        def connection(method, sock, address):
            if isinstance(address, tuple) and local(address[0]):
                return method(sock, address)
            return blocked()
        def resolve_local(host, *args, **kwargs):
            if local(host):
                return resolve(host, *args, **kwargs)
            return blocked()
        socket.socket.connect = lambda sock, address: connection(connect, sock, address)
        socket.socket.connect_ex = lambda sock, address: connection(connect_ex, sock, address)
        socket.getaddrinfo = resolve_local
        return
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    socket.getaddrinfo = blocked
