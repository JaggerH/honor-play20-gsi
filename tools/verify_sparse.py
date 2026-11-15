import struct, sys, hashlib
sp, gsi, sys_off = sys.argv[1], sys.argv[2], int(sys.argv[3])
f=open(sp,"rb"); h=struct.unpack("<IHHHHIIII",f.read(28)); BS=h[5]
pos=0; out=hashlib.sha256(); first=None; covered=0
for k in range(h[7]):
    t,_,n,ts=struct.unpack("<HHII",f.read(12))
    if first is None: first=t
    if t==0xCAC3:
        if pos==sys_off//BS+0 and covered: pass
        pos+=n; continue
    if t==0xCAC1: out.update(f.read(n*BS))
    elif t==0xCAC2: v=f.read(4); out.update(v*(BS//4)*n)
    pos+=n; covered+=n
g=hashlib.sha256(open(gsi,"rb").read()).hexdigest()
print("total_blks",h[6],"end",pos,"first_chunk",hex(first),"payload_blocks",covered)
print("reconstructed system == gsi:", out.hexdigest()==g)
