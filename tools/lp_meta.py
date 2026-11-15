import struct, hashlib, sys
GEO=4096; META0=GEO+2*4096
def parse(buf, off):
    h=buf[off:off+256]
    magic,maj,mnr,hsz=struct.unpack_from("<IHHI",h,0); assert magic==0x414C5030
    tsz,=struct.unpack_from("<I",h,44)
    descs=[struct.unpack_from("<III",h,80+12*i) for i in range(4)]
    return dict(hsz=hsz,tsz=tsz,descs=descs,maj=maj,mnr=mnr)
def dump(buf, off):
    m=parse(buf,off); t=off+m["hsz"]
    po,pn,ps=m["descs"][0]; eo,en,es=m["descs"][1]
    parts=[]; exts=[]
    for i in range(pn):
        e=buf[t+po+i*ps:t+po+(i+1)*ps]; name=e[:36].split(b"\0")[0].decode()
        attr,fe,ne,g=struct.unpack_from("<IIII",e,36); parts.append([name,attr,fe,ne,g,t+po+i*ps])
    for i in range(en):
        e=buf[t+eo+i*es:t+eo+(i+1)*es]; ns,tt,td,ts=struct.unpack("<QIQI",e); exts.append([ns,tt,td,ts,t+eo+i*es])
    return m,parts,exts
def fix_checksums(buf, off):
    m=parse(buf,off); t=off+m["hsz"]
    buf[off+48:off+80]=hashlib.sha256(bytes(buf[t:t+m["tsz"]])).digest()
    buf[off+12:off+44]=b"\0"*32
    buf[off+12:off+44]=hashlib.sha256(bytes(buf[off:off+m["hsz"]])).digest()
def verify(buf, off):
    m=parse(buf,off); t=off+m["hsz"]; h=bytearray(buf[off:off+m["hsz"]]); hc=bytes(h[12:44]); h[12:44]=b"\0"*32
    return hashlib.sha256(bytes(h)).digest()==hc and hashlib.sha256(bytes(buf[t:t+m["tsz"]])).digest()==bytes(buf[off+48:off+80])
if __name__=="__main__":
    buf=bytearray(open(sys.argv[1],"rb").read())
    maxsz,slots=struct.unpack_from("<II",buf,GEO+40)
    for off in (META0, META0+maxsz*slots):
        m,parts,exts=dump(buf,off); print("meta@",hex(off),"v%d.%d"%(m["maj"],m["mnr"]),"checksums ok:",verify(buf,off))
        for p in parts: print("  part",p[0],"first_ext",p[2],"n",p[3])
        for i,e in enumerate(exts): print("  ext",i,"sectors",e[0],"start",e[2])
