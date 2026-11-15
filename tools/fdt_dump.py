"""Minimal flattened-device-tree walker. usage: fdt_dump.py file.dtb <path-substring>"""
import struct, sys
def walk(d, want=None):
    magic,tot,off_struct,off_str,off_rsv,ver,lcv,bcpu,size_str,size_struct=struct.unpack(">10I",d[:40])
    p=off_struct; path=[]; res=[]
    while True:
        tok,=struct.unpack(">I",d[p:p+4]); p+=4
        if tok==1:
            e=d.index(b"\0",p); name=d[p:e].decode(); p=(e+4)&~3; path.append(name)
        elif tok==2: path.pop()
        elif tok==3:
            ln,no=struct.unpack(">II",d[p:p+8]); val_off=p+8; val=d[val_off:val_off+ln]
            nm=d[off_str+no:d.index(b"\0",off_str+no)].decode(); p=(val_off+ln+3)&~3
            res.append(("/".join(path), nm, val, val_off))
        elif tok==4: pass
        elif tok==9: return res
def main():
    for path,nm,val,vo in walk(open(sys.argv[1],"rb").read()):
        if sys.argv[2] in path:
            v=val.decode(errors="replace").replace("\0","|") if val and all(32<=c<127 or c==0 for c in val) else val.hex()[:40]
            print(hex(vo), path, nm, "=", v)

if __name__ == "__main__":
    main()
