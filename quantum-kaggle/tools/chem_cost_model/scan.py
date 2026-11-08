from cost import costs
import math
print("B sweep at R=8,C=44,brot=8: B heurT innerT Qheur(P+tmp) k2")
for B in [16,31,32,48,63,64,100,127,128,129,135,143,144,150,159,160,175,191,255]:
    try:
        c=costs(8,B,44,8); print(B,c['heurT'],c['innerT'],c['outP']+c['inP']+max(c['outTmp'],c['inTmp']),c['k2'])
    except Exception as e: print(B,'ERR',e)
print("brot sweep at (8,143,44)")
for b in range(5,13):
    c=costs(8,143,44,b); print(b,c['heurT'],c['innerT'],c['givT'],c['outP']+c['inP']+max(c['outTmp'],c['inTmp']),c['k2'])
print("RC sweep at B=143 brot=8 (R=8)")
for C in [20,30,36,40,44,48,56,64]:
    c=costs(8,143,C,8); print(8*C,c['heurT'],c['innerT'],c['outerT'],c['outP']+c['inP']+max(c['outTmp'],c['inTmp']))
print("R/C split at RC=352,B=143")
for R,C in [(1,352),(2,176),(4,88),(8,44),(11,32),(16,22),(22,16),(32,11)]:
    c=costs(R,143,C,8); print(R,C,c['heurT'],c['outP']+c['inP']+max(c['outTmp'],c['inTmp']),'rows',76+R*143)
# small-B regime at low brot
print("brot=7, B sweep")
for B in [33,63,64,65,100,127,128,143]:
    c=costs(8,B,44,7); print(B,c['heurT'],c['outP']+c['inP']+max(c['outTmp'],c['inTmp']),c['k2'])
