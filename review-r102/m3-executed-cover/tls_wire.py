"""In-process TLS 1.3 connections whose ciphertext lengths form the observation.

Each service connection is a real TLS 1.3 session (Python ssl over MemoryBIO).
We record the byte length of every ciphertext flight. Timing is not observed:
the replay has no network, so any timestamp would be an artefact.
"""
import os
import ssl
import subprocess
import tempfile

_CERT = None


def _cert():
    global _CERT
    if _CERT is None:
        d = tempfile.mkdtemp()
        key, crt = os.path.join(d, "k.pem"), os.path.join(d, "c.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", key, "-out", crt, "-days", "2", "-subj", "/CN=svc"],
                       check=True, capture_output=True)
        _CERT = (crt, key)
    return _CERT


def _pump(src_bio, dst_bio):
    data = src_bio.read()
    if data:
        dst_bio.write(data)
    return len(data)


class Conn:
    def __init__(self, service):
        crt, key = _cert()
        sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        sctx.minimum_version = ssl.TLSVersion.TLSv1_3
        sctx.load_cert_chain(crt, key)
        cctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        cctx.minimum_version = ssl.TLSVersion.TLSv1_3
        cctx.check_hostname = False
        cctx.verify_mode = ssl.CERT_NONE
        self.c_in, self.c_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.s_in, self.s_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.c = cctx.wrap_bio(self.c_in, self.c_out, server_hostname=service)
        self.s = sctx.wrap_bio(self.s_in, self.s_out, server_side=True)
        self.service = service
        self._handshake()

    def _handshake(self):
        for _ in range(10):
            done = 0
            for obj in (self.c, self.s):
                try:
                    obj.do_handshake()
                    done += 1
                except ssl.SSLWantReadError:
                    pass
            _pump(self.c_out, self.s_in)
            _pump(self.s_out, self.c_in)
            if done == 2:
                break

    def exchange(self, request, response):
        """Send request then response; return (client->server bytes, server->client bytes)."""
        self.c.write(request)
        up = _pump(self.c_out, self.s_in)
        got = b""
        while len(got) < len(request):
            got += self.s.read(65536)
        self.s.write(response)
        down = _pump(self.s_out, self.c_in)
        got = b""
        while len(got) < len(response):
            got += self.c.read(65536)
        return up, down


def http_frame(service, path, body, quantum):
    if quantum:
        pad = (-len(body)) % quantum
        body = body + b" " * pad
    head = (f"POST /{path} HTTP/1.1\r\nHost: {service}\r\n"
            f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n").encode()
    return head + body
