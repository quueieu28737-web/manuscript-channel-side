"""Parser-only synthetic PCAP fixture: reuse one TCP port pair, new ISNs.

No packets are sent and no model is called. These are TLS-shaped dummy bytes,
not an encrypted network experiment or publication outcome.
"""
import ipaddress,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from common import H,save,sha,now
from capture_tcp_generation import capture_records

def checksum(b):
    if len(b)%2:b+=b'\0'
    n=sum(struct.unpack('!'+str(len(b)//2)+'H',b))
    while n>>16:n=(n&65535)+(n>>16)
    return (~n)&65535

def packet(src,dst,seq,ack,flags,payload=b''):
    ip=ipaddress.ip_address('127.0.0.1').packed
    tcp=struct.pack('!HHIIBBHHH',src,dst,seq,ack,5<<4,flags,65535,0,0)+payload
    c=checksum(ip+ip+b'\0\x06'+struct.pack('!H',len(tcp))+tcp)
    tcp=tcp[:16]+struct.pack('!H',c)+tcp[18:]
    hdr=struct.pack('!BBHHHBBH4s4s',0x45,0,20+len(tcp),0,0,64,6,0,ip,ip)
    hdr=hdr[:10]+struct.pack('!H',checksum(hdr))+hdr[12:]
    return hdr+tcp

def main():
    raw=H/'private-run/parser-port-reuse-development';(raw/'capture').mkdir(parents=True,exist_ok=False)
    path=raw/'capture/traffic.pcapng'  # reader detects legacy PCAP by magic
    data=bytearray(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,101))
    for gen,seq in [(0,1000),(1,200000)]:
        frames=[(55000,41120,seq,0,2,b''),(41120,55000,seq+10000,seq+1,18,b''),
                (55000,41120,seq+1,seq+10001,16,b''),
                (55000,41120,seq+1,seq+10001,24,b'\x17\x03\x03\x00\x03abc'),
                (41120,55000,seq+10001,seq+9,24,b'\x17\x03\x03\x00\x03xyz'),
                (55000,41120,seq+9,seq+10009,20,b'')]
        for i,fr in enumerate(frames):
            b=packet(*fr);data.extend(struct.pack('<IIII',100+gen*300,i*100000,len(b),len(b)));data.extend(b)
    path.write_bytes(data);streams=capture_records(raw)
    assert len(streams[55000,41120])==len(streams[41120,55000])==2
    assert all([[v[0],v[1]] for v in s['records']]==[[23,8]] for flows in streams.values() for s in flows)
    save(H/'verification/tcp-generation-parser-readiness.json',{'status':'PASS','utc':now(),'test':'Two synthetic TCP generations sharing ports, no network or LLM execution',
        'capture_sha256':sha(path),'decoder_sha256':sha(H/'verification/capture_tcp_generation.py'),
        'test_sha256':sha(__file__),'streams':sum(len(v) for v in streams.values())})
    print('TCP_GENERATION_REUSE_PARSER_PASS')

if __name__=='__main__':main()
