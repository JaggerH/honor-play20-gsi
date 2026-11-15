import struct, sys, hashlib
gsi, out, super_size, sys_off = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
BS=4096; MAXRAW=4*1024*1024//BS
tot=super_size//BS; off_blk=sys_off//BS
data=open(gsi,"rb").read(); assert len(data)%BS==0
nblk=len(data)//BS
chunks=[]  # (type, nblocks, payload)
chunks.append((0xCAC3, off_blk, b""))
zero=bytes(BS); i=0
while i<nblk:
    z = data[i*BS:(i+1)*BS]==zero
    j=i
    while j<nblk and (data[j*BS:(j+1)*BS]==zero)==z and (z or j-i<MAXRAW): j+=1
    chunks.append((0xCAC2,j-i,b"\0\0\0\0") if z else (0xCAC1,j-i,data[i*BS:j*BS]))
    i=j
rest=tot-off_blk-nblk; assert rest>0
chunks.append((0xCAC3,rest,b""))
assert sum(c[1] for c in chunks)==tot
with open(out,"wb") as f:
    f.write(struct.pack("<IHHHHIIII",0xED26FF3A,1,0,28,12,BS,tot,len(chunks),0))
    for t,n,p in chunks: f.write(struct.pack("<HHII",t,0,n,12+len(p))); f.write(p)
print("chunks",len(chunks),"raw",sum(c[1] for c in chunks if c[0]==0xCAC1),"fill",sum(c[1] for c in chunks if c[0]==0xCAC2),"blocks")
