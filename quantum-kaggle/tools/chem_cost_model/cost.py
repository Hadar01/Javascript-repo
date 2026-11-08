import math, numpy as np, sys
def QR(L,M1):
    k=0.5*np.log2(L/M1); k=max(k,0)
    v=lambda k: L/2.0**k + M1*(2.0**k-1)
    ks=[math.floor(k),math.ceil(k)]; ko=ks[int(np.argmin([v(x) for x in ks]))]
    return int(ko), int(math.ceil(v(ko)))
def QI(L):
    k=max(0.5*np.log2(L),0); v=lambda k: L/2.0**k+2.0**k-1
    ks=[math.floor(k),math.ceil(k)]; ko=ks[int(np.argmin([v(x) for x in ks]))]
    return int(ko), int(math.ceil(v(ko)))
def k2(R,B,C,N,chi,beta):
    b2=math.ceil(math.log2(B))+chi+1
    k=QR(R*C*B,b2)[0]
    for j in range(k+1):
        kn=k-j
        if math.ceil(math.log2(R*C*math.ceil(B/2**kn)))+(2**kn-1)*b2 < beta*(N-1):
            return kn,b2
    raise ValueError
def costs(R,B,C,beta,N=76,chi=10):
    Xo=N+R*C; lX=math.ceil(math.log2(Xo)); b1=lX+chi
    outerT=8*lX + QR(Xo,b1)[1]+b1 + QI(Xo)[1]+b1+1
    kk,b2=k2(R,B,C,N,chi,beta)
    if B<2**kk:
        for _ in range(kk):
            kk-=1
            if B>=2**kk: break
    RC=R*C
    fq=RC*math.ceil((B+1)/2**kk)+2**kk*b2
    k4,qi=QR(RC,B+1)
    fqd=qi+(B+1)+N+b2
    ub=4*math.ceil(math.log2(B+1))
    innerT=fq+fqd+2*ub
    givT=2*(N-1)*(2*beta-1)
    # qubits
    kq=QR(Xo,b1)[0]
    outP=b1+chi+lX+2; outTmp=math.ceil(math.log2(Xo/2**kq))+2**kq*b1+max(0,lX-2)
    kk2,_=k2(R,B,C,N,chi,beta)
    inP=b2+chi+math.ceil(math.log2(R))+2 + math.ceil(math.log2(B+1))+2
    inTmp=max(0,math.ceil(math.log2(B+1))-2)+math.ceil(math.log2(RC*math.ceil((B+1)/2**kk2)))+(2**kk2-1)*b2
    return dict(outerT=outerT,innerT=innerT,givT=givT,heurT=outerT+innerT+givT,outP=outP,inP=inP,outTmp=outTmp,inTmp=inTmp,k2=kk2,k2T=kk)
if __name__=="__main__":
    for args in [(65,60,60,12),(65,60,60,16),(8,143,45,8),(8,143,44,8),(9,143,40,8),(8,143,45,9),(8,143,45,7),(8,143,45,10)]:
        c=costs(*args); print(args,c)
