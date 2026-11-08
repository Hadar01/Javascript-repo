import math
REF=3355599588.3155365; LAM=46.8926
def loader_pass(A,J,b_eff=7,rel=0.857,scratch=0):
    sel=math.ceil(math.log2(A)); best=None
    for m in range(2,8):
        cache=math.ceil(math.ceil(A/2**m)*72/77)
        if sel+8*J+cache+scratch>128: continue
        K=math.ceil(75/J); c=K*(cache+J*b_eff*(2**m-1)/2*rel)
        if best is None or c<best[0]: best=(c,m,K,cache)
    return best
# calibrate: public (8,143,44) J5 -> model vs actual 4152/pass
def total(R,B,C,J,brot=8,calib=4152/4455):
    h=costs(R,B,C,brot); A=76+R*B
    lp=loader_pass(A,J)
    if lp is None: return None
    T=h['heurT']+2*lp[0]*calib
    Q=h['outP']+h['inP']+brot*J+max(h['outTmp'],h['inTmp'])
    return T,Q,REF/(LAM*T*Q),lp[1:]
print('model public',total(8,143,44,5))
for J in [1,2,3,4,5,6,7]:
    print('J',J,total(8,143,44,J))
for R,C in [(1,352),(2,176),(4,88),(6,59),(7,50),(8,44)]:
    for J in [5,6,7,8]:
        t=total(R,143,C,J)
        if t: print('R',R,'C',C,'J',J,'rows',76+R*143,[round(x,1) if isinstance(x,float) else x for x in t])
