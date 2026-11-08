import numpy as np, sys
N=76; ETA=113; EUP=-22140.27335
oei=np.load('oei.npy'); tei=np.load('tei.npy').astype(np.float64); ecore=float(np.load('ecore.npy'))
fs=np.load('../data/verifiers/dfthcsos/FeMoCo76o113e.fixed_shifts.npz',allow_pickle=False)
def sym(lower):
    m=np.zeros((N,N),np.float32); r,c=np.tril_indices(N); m[r,c]=lower.astype(np.float32); return m+m.T-np.diag(np.diag(m))
S=sym(fs['Hsym_lower']).astype(np.float64); beta1=float(fs['H1_I'])-0.5*np.trace(S)
def decode(words,edges,brot):
    ang=words/(1<<(brot-1)); V=np.zeros((len(words),N)); V[:,0]=1
    for t,(p,c) in enumerate(edges):
        a=V[:,p].copy(); b=V[:,c].copy(); th=np.pi*ang[:,t]
        V[:,p]=np.cos(th)*a-np.sin(th)*b; V[:,c]=np.sin(th)*a+np.cos(th)*b
    return V
def evaluate(w,Wb,U2,want_err2=True):
    # w (R,B,C), Wb = W (R,C) native, U2 (R,B,N) unit
    X=np.einsum('tjp,tjq,tjl->tlpq',U2,U2,w,optimize=True)
    X=np.tril(X)+np.swapaxes(np.tril(X,k=-1),-1,-2)
    h1=oei-0.5*np.einsum('prrq->pq',tei)
    h1p=h1-0.5*ETA*S+beta1*np.eye(N)-np.einsum('rc,rcpq->pq',Wb,X)
    ev=np.linalg.eigvalsh(h1p)
    lam1=np.abs(ev).sum()
    wB=Wb+w.sum(1); a=np.abs(w).sum(1)
    lam2=0.25*np.sum((a+np.abs(wB))**2)
    L=lam1+lam2
    Esos=ecore-ETA*beta1-(lam1-ev.sum())-0.5*np.sum(Wb**2)
    Eg=EUP-Esos
    le=np.sqrt(Eg*(2*L-Eg))
    out=dict(lam1=lam1,lam2=lam2,Lambda=L,E_gap=Eg,lambda_eff=le,negsum=(lam1-ev.sum())/2,halfW2=0.5*np.sum(Wb**2),
             trh1p=ev.sum(), D=0.5*np.sum(a**2-(w.sum(1))**2), wBpart=0.25*np.sum(np.abs(wB)**2+2*a*np.abs(wB)), apart=0.25*np.sum(a**2),
             const=EUP-ecore+ETA*beta1, nneg=(ev<0).sum())
    if want_err2:
        d=np.einsum('rcpq,rcst->pqst',X,X,optimize=True)-tei
        di=np.arange(N); d[:,:,di,di]-=0.5*S[:,:,None]; d[di,di,:,:]-=0.5*S[None,:,:]
        out['error_2']=float(np.linalg.norm(d.ravel()))
    return out,ev
if __name__=='__main__':
    z=np.load(sys.argv[1],allow_pickle=False)
    w=z['W'].astype(np.float64); W=z['H2_I'].astype(np.float64)-w.sum(1)
    R,B,C=w.shape
    if 'angle_words' in z.files:
        brot=int(sys.argv[2]) if len(sys.argv)>2 else 12
        V=decode(z['angle_words'],z['tree_edges'],brot); U2=V[N:].reshape(R,B,N)
    else:
        U=z['U'].astype(np.float64); U2=U/np.linalg.norm(U,axis=2,keepdims=True)
    o,ev=evaluate(w,W,U2)
    for k,v in o.items(): print(k,v)
    print('eig range',ev.min(),ev.max())
    # unrounded
    U=z['U'].astype(np.float64); U2=U/np.linalg.norm(U,axis=2,keepdims=True)
    o2,_=evaluate(w,W,U2,False); print('unrounded lambda_eff',o2['lambda_eff'],'Lambda',o2['Lambda'],'Egap',o2['E_gap'])
