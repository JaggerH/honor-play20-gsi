import gzip, sys
def parse(data):
    off=0; out=[]
    while True:
        h=data[off:off+110]; assert h[:6]==b"070701", (off,h[:6])
        f=[int(h[6+8*i:14+8*i],16) for i in range(13)]
        namesize, filesize = f[11], f[6]
        name=data[off+110:off+110+namesize-1].decode()
        p=(off+110+namesize+3)&~3
        body=data[p:p+filesize]
        out.append((f,name,body))
        off=(p+filesize+3)&~3
        if name=="TRAILER!!!": return out
def build(entries):
    o=bytearray()
    for f,name,body in entries:
        f=list(f); f[6]=len(body); f[11]=len(name)+1
        o+=b"070701"+b"".join(b"%08X"%x for x in f)+name.encode()+b"\0"
        while len(o)%4: o+=b"\0"
        o+=body
        while len(o)%4: o+=b"\0"
    return bytes(o)
if __name__=="__main__":
    e=parse(gzip.decompress(open(sys.argv[1],"rb").read()))
    for f,n,b in e: print(oct(f[1]), len(b), n)
