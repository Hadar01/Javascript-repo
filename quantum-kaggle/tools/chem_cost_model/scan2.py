res=[]
for B in [7,8,15,16,31,32,63,64,127,129,143]:
  for R in [4,8,16,24,32,38,48,64,76,96,128,152]:
    for C in [2,3,4,5,6,8,11,16,22,32,44,64,88]:
      RC=R*C
      if not (300<=RC<=520): continue
      try: c=costs(R,B,C,8)
      except Exception: continue
      Q=c['outP']+c['inP']+max(c['outTmp'],c['inTmp'])+40
      res.append((B,R,C,RC,R*B,c['heurT'],c['innerT'],Q,c['k2']))
seen=set()
for r in sorted(res,key=lambda r:(r[0],r[3])):
    key=(r[0],r[3]//50)
    if key in seen: continue
    seen.add(key); print(r)
