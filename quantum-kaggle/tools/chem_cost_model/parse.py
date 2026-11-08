import numpy as np, sys, time
t=time.time()
path=sys.argv[1]
raw=open(path,'rb').read()
i=raw.find(b'&END'); body=raw[i+4:]
a=np.array(body.split(),dtype=np.float64).reshape(-1,5)
N=76
c=a[:,0]; idx=a[:,1:].astype(int)
oei=np.zeros((N,N)); tei=np.zeros((N,N,N,N),dtype=np.float32)
four=(idx[:,2]>0); two=(idx[:,0]>0)&(idx[:,2]==0); core=(idx[:,0]==0)
ecore=c[core][0]
p,q=idx[two,0]-1,idx[two,1]-1; oei[p,q]=c[two]; oei[q,p]=c[two]
I,J,K,L=[idx[four,k]-1 for k in range(4)]; v=c[four].astype(np.float32)
for (x,y,z,w) in [(I,J,K,L),(J,I,K,L),(I,J,L,K),(J,I,L,K),(K,L,I,J),(L,K,I,J),(K,L,J,I),(L,K,J,I)]:
    tei[x,y,z,w]=v
np.save('oei.npy',oei); np.save('tei.npy',tei); np.save('ecore.npy',np.array(ecore))
print('parsed',time.time()-t, ecore, four.sum(), two.sum())
