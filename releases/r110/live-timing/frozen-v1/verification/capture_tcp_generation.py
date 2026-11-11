"""Reassemble ciphertext records by Wireshark TCP generation, not port alone.

Ephemeral ports can recur during a multi-hour capture. tcp.stream is used solely
by the independent evaluator, never by any attack feature or role classifier.
"""
import collections,subprocess
def capture_records(raw):
    dst=raw/'capture/tcp-fields-generations.tsv'
    if not dst.exists():
        with dst.open('xb') as f,(raw/'capture/tshark-generations.stderr.log').open('xb') as err:
            subprocess.run([r'C:\Program Files\Wireshark\tshark.exe','-n','-r',str(raw/'capture/traffic.pcapng'),
              '-o','tcp.relative_sequence_numbers:FALSE','-T','fields','-e','frame.time_epoch','-e','tcp.srcport',
              '-e','tcp.dstport','-e','tcp.seq_raw','-e','tcp.payload','-e','tcp.stream'],stdout=f,stderr=err,check=True)
    streams={}
    for line in dst.open(encoding='utf-8'):
        cols=line.rstrip('\n').split('\t')
        if len(cols)<6 or not cols[4]:continue
        epoch,src,dstp,seq,payload,generation=cols[:6]
        key=(int(src),int(dstp),int(generation));seq=int(seq);b=bytes.fromhex(payload.replace(':',''));t=float(epoch)
        if key not in streams:streams[key]={'expected':seq,'pending':{},'buf':bytearray(),'times':[],'records':[],'tcp_stream':int(generation)}
        s=streams[key];end=seq+len(b)
        if end<=s['expected']:continue
        if seq<s['expected']:b=b[s['expected']-seq:];seq=s['expected']
        s['pending'][seq]=(b,t)
        while s['expected'] in s['pending']:
            b,t=s['pending'].pop(s['expected']);s['expected']+=len(b);s['buf'].extend(b);s['times'].extend([t]*len(b))
            while len(s['buf'])>=5:
                size=5+int.from_bytes(s['buf'][3:5],'big');assert size<=18437
                if len(s['buf'])<size:break
                s['records'].append([s['buf'][0],size,max(s['times'][:size])])
                del s['buf'][:size];del s['times'][:size]
    by_pair=collections.defaultdict(list)
    for (src,dstp,generation),s in streams.items():
        assert not s['pending'],('missing TCP range',src,dstp,generation)
        by_pair[src,dstp].append(s)
    return by_pair
