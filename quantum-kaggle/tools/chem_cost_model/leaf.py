import numpy as np
N=76
ev=np.load('sup_ev.npy'); V=np.load('sup_V.npy').astype(np.float64)
print('top eig',ev[:8])
for k in range(4):
    L=(V[:,k]*np.sqrt(ev[k])).reshape(N,N); L=0.5*(L+L.T)
    w=np.linalg.eigvalsh(L); w=w[np.argsort(-np.abs(w))]
    # error of L⊗L truncated to rank r: ||L⊗L - Lr⊗Lr|| = sqrt(|L|^4 - 2 (L.Lr)^2 + |Lr|^4) with L.Lr=|Lr|^2
    tot=np.sum(w**2)
    out=[]
    for r in [8,15,16,30,45,60,70,76]:
        p=np.sum(w[:r]**2); out.append(f'r{r}:{1e3*np.sqrt(max(tot**2-p**2,0)):.1f}')
    print('leaf',k,'eig of L (top5)',np.round(w[:5],3),'min',np.round(w[-3:],4),' '.join(out),'mHa')
