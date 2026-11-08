import numpy as np, time
N=76
tei=np.load('tei.npy').astype(np.float64)
fs=np.load('../data/verifiers/dfthcsos/FeMoCo76o113e.fixed_shifts.npz',allow_pickle=False)
r,c=np.tril_indices(N); m=np.zeros((N,N),np.float32); m[r,c]=fs['Hsym_lower'].astype(np.float32); S=(m+m.T-np.diag(np.diag(m))).astype(np.float64)
M=tei.copy(); d=np.arange(N)
M[:,:,d,d]+=0.5*S[:,:,None]; M[d,d,:,:]+=0.5*S[None,:,:]
M=M.reshape(N*N,N*N); M=0.5*(M+M.T)
t=time.time(); ev,V=np.linalg.eigh(M); print('eigh',time.time()-t)
ev=ev[::-1]; V=V[:,::-1]
np.save('sup_ev.npy',ev); np.save('sup_V.npy',V[:,:1000].astype(np.float32))
nM=np.linalg.norm(M)
print('||M||',nM,'neg eig mass (mHa)',1e3*np.sqrt(np.sum(ev[ev<0]**2)), 'num pos',(ev>1e-9).sum())
for K in [76,150,200,300,352,414,456,600,800]:
    print('rank',K,'trunc err mHa',1e3*np.sqrt(max(0,nM**2-np.sum(ev[:K]**2))))
def err(Xs):
    Xm=Xs.reshape(len(Xs),-1).T
    G=Xm.T@Xm; MX=M@Xm
    e2=nM**2-2*np.sum(Xm*MX)+np.sum(G**2); return 1e3*np.sqrt(max(e2,0))
for K in [76,150,300,456]:
    L=(V[:,:K]*np.sqrt(np.maximum(ev[:K],0))).T.reshape(K,N,N); L=0.5*(L+np.swapaxes(L,1,2))
    w,U=np.linalg.eigh(L)
    for Bk in [8,15,30,60,76]:
        idx=np.argsort(-np.abs(w),axis=1)[:,:Bk]
        X=np.zeros_like(L)
        for k in range(K):
            ww=w[k,idx[k]]; uu=U[k][:,idx[k]]; X[k]=(uu*ww)@uu.T
        print(f'K={K} leaves, per-leaf rank {Bk} ({K*Bk} vectors): err {err(X):.2f} mHa')
