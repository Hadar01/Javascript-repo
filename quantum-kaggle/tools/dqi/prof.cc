// Independent bit-packed kickmix simulator + profiler for DQI .kmb circuits (Agent B, own code).
// Semantics follow kickmix sim.h: condition stack (PUSH snapshots base&bit), *_IF per-op conditions,
// HMR = random bit b, phase ^= q&b, q=0; R = phase ^= q&rand, q=0. Counts executed Toffoli-like (CCX/CCZ/CSWAP)
// per shot as popcount(cond) like the official counter.
// usage: prof <kmb> <inputs prefix> <nshots> <seg.u16 file or -> <out prefix> [timeline_window]
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>
#include <algorithm>
using namespace std;
typedef uint64_t u64;
static u64 rd64(FILE*f){u64 x;if(fread(&x,8,1,f)!=1){fprintf(stderr,"eof\n");exit(1);}return x;}
static uint32_t rd32(FILE*f){uint32_t x;if(fread(&x,4,1,f)!=1){fprintf(stderr,"eof\n");exit(1);}return x;}
template<class T> static vector<T> blob(FILE*f,u64 code,u64 cnt){u64 c=rd64(f);if(c!=code){fprintf(stderr,"bad code %llu\n",(unsigned long long)c);exit(1);}u64 sz=rd64(f);if(sz!=cnt*sizeof(T)){fprintf(stderr,"bad size\n");exit(1);}vector<T> v(cnt);if(cnt&&fread(v.data(),sizeof(T),cnt,f)!=cnt){exit(1);}return v;}
struct Reg{string name;vector<uint32_t> ids;};
static u64 s[4];
static inline u64 rotl(u64 x,int k){return (x<<k)|(x>>(64-k));}
static inline u64 rnd(){u64 r=rotl(s[1]*5,7)*9;u64 t=s[1]<<17;s[2]^=s[0];s[3]^=s[1];s[1]^=s[2];s[0]^=s[3];s[2]^=t;s[3]=rotl(s[3],45);return r;}
int main(int argc,char**argv){
  if(argc<6){fprintf(stderr,"usage\n");return 1;}
  const char*kmb=argv[1];string inp=argv[2];long N=atol(argv[3]);const char*segf=argv[4];string out=argv[5];
  long TW=argc>6?atol(argv[6]):65536;
  int W=(N+63)/64; if(N%64){fprintf(stderr,"N must be multiple of 64\n");return 1;}
  FILE*f=fopen(kmb,"rb"); unsigned char magic[16]; if(fread(magic,1,16,f)!=16) return 1;
  uint32_t ver=rd32(f),nq=rd32(f),nb=rd32(f),nreg=rd32(f); if(ver!=2) return 2;
  u64 nops=rd64(f),nqqq=rd64(f),nqq=rd64(f),nq1=rd64(f),nb1=rd64(f),nc=rd64(f),nang=rd64(f),ntag=rd64(f),ntagch=rd64(f);
  vector<Reg> regs(nreg);
  for(auto&r:regs){rd64(f);rd64(f);uint32_t nl=rd32(f),rl=rd32(f);r.name.resize(nl);if(fread(&r.name[0],1,nl,f)!=nl)return 3;r.ids.resize(rl);if(fread(r.ids.data(),4,rl,f)!=rl)return 3;}
  if(rd64(f)!=1) return 4; if(rd64(f)!=nops) return 4;
  vector<uint8_t> op(nops); if(fread(op.data(),1,nops,f)!=nops) return 5;
  auto qqq0=blob<uint32_t>(f,2,nqqq),qqq1=blob<uint32_t>(f,3,nqqq),qqq2=blob<uint32_t>(f,4,nqqq);
  auto qq0=blob<uint32_t>(f,5,nqq),qq1=blob<uint32_t>(f,6,nqq),q0=blob<uint32_t>(f,7,nq1);
  auto b0=blob<uint32_t>(f,8,nb1),bc=blob<uint32_t>(f,9,nc);
  fclose(f);
  if(nang){fprintf(stderr,"Z_POW present\n");}
  // segments
  vector<uint16_t> seg(nops,0); int nseg=1;
  if(strcmp(segf,"-")){FILE*g=fopen(segf,"rb");if(fread(seg.data(),2,nops,g)!=nops)return 6;fclose(g);for(auto x:seg)nseg=max(nseg,(int)x+1);}
  // registers
  vector<uint32_t> synq, mbits; // syndrome qubit ids in S0..S69 order, E bits in E0..E4094 order
  for(int i=0;i<70;i++){string nm="S"+to_string(i);for(auto&r:regs)if(r.name==nm)for(auto id:r.ids)synq.push_back(id&0x7fffffff);}
  for(int j=0;j<4095;j++){string nm="E"+to_string(j);for(auto&r:regs)if(r.name==nm)for(auto id:r.ids)mbits.push_back(id&0x7fffffff);}
  if(synq.size()!=840||mbits.size()!=49140){fprintf(stderr,"reg size %zu %zu\n",synq.size(),mbits.size());return 7;}
  // inputs
  vector<uint16_t> syn(N*70), mb(N*4095); vector<uint8_t> ph(N);
  {FILE*g=fopen((inp+".syn").c_str(),"rb");if(fread(syn.data(),2,N*70,g)!=(size_t)N*70)return 8;fclose(g);}
  {FILE*g=fopen((inp+".mbuc").c_str(),"rb");if(fread(mb.data(),2,N*4095,g)!=(size_t)N*4095)return 8;fclose(g);}
  {FILE*g=fopen((inp+".phase").c_str(),"rb");if(fread(ph.data(),1,N,g)!=(size_t)N)return 8;fclose(g);}
  vector<u64> Q((size_t)nq*W,0), B((size_t)nb*W,0), phase(W,0), tmp(W);
  auto qv=[&](uint32_t q){return &Q[(size_t)q*W];}; auto bv=[&](uint32_t b){return &B[(size_t)b*W];};
  for(long sh=0;sh<N;sh++){int w=sh>>6;u64 bit=1ull<<(sh&63);
    for(int i=0;i<70;i++){uint16_t v=syn[sh*70+i];for(int k=0;k<12;k++)if((v>>k)&1)qv(synq[i*12+k])[w]|=bit;}
    for(int j=0;j<4095;j++){uint16_t v=mb[sh*4095+j];for(int k=0;k<12;k++)if((v>>k)&1)bv(mbits[j*12+k])[w]|=bit;}}
  vector<u64> Q0=Q;
  s[0]=0x9E3779B97F4A7C15ull^(u64)atoll(getenv("PROF_SEED")?getenv("PROF_SEED"):"0");s[1]=0xD1B54A32D192ED03ull;s[2]=0x8CB92BA72F3D8DD7ull;s[3]=0x1234567ull;
  // condition stack
  vector<vector<u64>> cstack; vector<u64> base(W,~0ull), cond(W);
  // liveness
  vector<uint8_t> dirty(nq,0); long live=0, livews=0; 
  auto upd=[&](uint32_t q){u64 o=0;u64*p=qv(q);for(int w=0;w<W;w++)o|=p[w];uint8_t d=o!=0;if(d!=dirty[q]){long dl=d?1:-1;live+=dl;if(q>=840)livews+=dl;dirty[q]=d;}};
  for(uint32_t q=0;q<nq;q++)upd(q);
  // stats
  vector<double> segtof(nseg,0),segtofstatic(nseg,0),seghmr(nseg,0),segops(nseg,0); vector<long> segpeak(nseg,0),segpeakws(nseg,0),segpeakop(nseg,-1);
  vector<long> segfirst(nseg,-1), seglast(nseg,-1);
  long gpeak=0,gpeakop=0; const int HL=860; vector<vector<double>> hist(nseg,vector<double>(nq-HL+1,0)); vector<vector<long>> entries(nseg,vector<long>(nq-HL+1,0)); long prevlive=live; vector<long> dumpops; if(getenv("DUMP_OPS")){string ds=getenv("DUMP_OPS");size_t st=0;while(st<ds.size()){size_t e=ds.find(',',st);if(e==string::npos)e=ds.size();dumpops.push_back(atol(ds.substr(st,e-st).c_str()));st=e+1;}} FILE*dumpf=fopen((out+"_dumps.txt").c_str(),"w"); size_t di=0; sort(dumpops.begin(),dumpops.end()); vector<double> qlive(nq,0); vector<long> seg_of_dump; vector<uint8_t> gpeakmap(nq,0);
  vector<long> tl_peak, tl_peakws; vector<double> tl_tof; long wpeak=0,wpeakws=0; double wtof=0;
  size_t iqqq=0,iqq=0,iq=0,ib=0,ic=0; double tottof=0; vector<uint32_t> fire3(nqqq,0); vector<uint64_t> fireop(nqqq,0); vector<uint8_t> cls(nqqq,0); bool doCls=getenv("CLS_OUT")!=nullptr;
  auto pc=[&](const u64*c){long t=0;for(int w=0;w<W;w++)t+=__builtin_popcountll(c[w]);return t;};
  for(u64 k=0;k<nops;k++){
    uint8_t t=op[k]; int sg=seg[k]; segops[sg]+=1; if(segfirst[sg]<0)segfirst[sg]=k; seglast[sg]=k;
    bool hasc=(t&0x80)&&t!=0x81;
    memcpy(cond.data(),base.data(),8*W);
    if(hasc){u64*c=bv(bc[ic++]);for(int w=0;w<W;w++)cond[w]&=c[w];}
    uint8_t bt=t&0x7f; int nqt=(t>>4)&3; bool hb=t&0x40;
    if(t==0x81){u64*c=bv(bc[ic++]);for(int w=0;w<W;w++)base[w]&=c[w];cstack.push_back(base);}
    else if(t==0x01){if(!cstack.empty())cstack.pop_back();if(cstack.empty())std::fill(base.begin(),base.end(),~0ull);else base=cstack.back();}
    else if(bt==0x06||bt==0x07){}
    else if(nqt==3){uint32_t a=qqq0[iqqq],b=qqq1[iqqq],c=qqq2[iqqq];iqqq++;
      long e=pc(cond.data()); segtof[sg]+=e; segtofstatic[sg]+=1; tottof+=e; wtof+=e;
      u64*A=qv(a),*Bq=qv(b),*C=qv(c);
      if((bt&0x0f)==1){if(doCls){u64 any_tb=0,any_ta=0,any_p=0,d1=0,d2=0;for(int w=0;w<W;w++){u64 p=cond[w]&A[w]&Bq[w];any_tb|=C[w]&cond[w];any_ta|=(C[w]^p)&cond[w];any_p|=p;d1|=p^(A[w]&cond[w]);d2|=p^(Bq[w]&cond[w]);}
        uint8_t f=0; if(!any_ta&&any_tb)f|=1; if(!any_p)f|=2; if(!d1)f|=4; if(!d2)f|=8; if(!any_tb)f|=16; cls[iqqq-1]=f; fireop[iqqq-1]=k;}
        for(int w=0;w<W;w++)C[w]^=cond[w]&A[w]&Bq[w];upd(c);}
      else if((bt&0x0f)==0){for(int w=0;w<W;w++)phase[w]^=cond[w]&A[w]&Bq[w]&C[w];}
      else {long fc=0;for(int w=0;w<W;w++){u64 cc=A[w]&cond[w];fc+=__builtin_popcountll(cc);u64 x=(Bq[w]^C[w])&cc;Bq[w]^=x;C[w]^=x;}upd(b);upd(c);fire3[iqqq-1]=fc;fireop[iqqq-1]=k;}
    } else if(nqt==2){uint32_t a=qq0[iqq],b=qq1[iqq];iqq++;u64*A=qv(a),*Bq=qv(b);
      if((bt&0x0f)==1){for(int w=0;w<W;w++)Bq[w]^=cond[w]&A[w];upd(b);}
      else if((bt&0x0f)==0){for(int w=0;w<W;w++)phase[w]^=cond[w]&A[w]&Bq[w];}
      else if((bt&0x0f)==2){for(int w=0;w<W;w++){u64 x=(A[w]^Bq[w])&cond[w];A[w]^=x;Bq[w]^=x;}upd(a);upd(b);}
      else {fprintf(stderr,"unk2 %x\n",t);return 9;}
    } else if(nqt==1){uint32_t a=q0[iq++];u64*A=qv(a);
      if(hb){ // HMR
        uint32_t bb=b0[ib++];u64*Bb=bv(bb); seghmr[sg]+=pc(cond.data());
        for(int w=0;w<W;w++){u64 r=rnd();u64 bnew=(Bb[w]&~cond[w])|(r&cond[w]);phase[w]^=A[w]&bnew&cond[w];A[w]&=~cond[w];Bb[w]=bnew;}upd(a);
      } else if((bt&0x0f)==0){for(int w=0;w<W;w++)phase[w]^=cond[w]&A[w];}
      else if((bt&0x0f)==1){for(int w=0;w<W;w++)A[w]^=cond[w];upd(a);}
      else if((bt&0x0f)==2){for(int w=0;w<W;w++){phase[w]^=A[w]&rnd()&cond[w];A[w]&=~cond[w];}upd(a);}
      else {fprintf(stderr,"unk1 %x\n",t);return 9;}
    } else if(hb){uint32_t bb=b0[ib++];u64*Bb=bv(bb);int kk=bt&0x0f;
      if(kk==0)for(int w=0;w<W;w++)Bb[w]&=~cond[w]; else if(kk==1)for(int w=0;w<W;w++)Bb[w]|=cond[w]; else if(kk==2)for(int w=0;w<W;w++)Bb[w]^=cond[w];
    } else if(bt==0x00){for(int w=0;w<W;w++)phase[w]^=cond[w];}
    else {fprintf(stderr,"unk %x\n",t);return 9;}
    if(live>segpeak[sg]){segpeak[sg]=live;segpeakop[sg]=k;}
    if(livews>segpeakws[sg])segpeakws[sg]=livews;
    if(live>gpeak){gpeak=live;gpeakop=k;memcpy(gpeakmap.data(),dirty.data(),nq);}
    {long l=live<HL?HL:live; hist[sg][l-HL]+=1; if(live>prevlive){for(long L=max(prevlive+1,(long)HL);L<=live;L++)entries[sg][L-HL]++;} prevlive=live;}
    while(di<dumpops.size()&&(long)k==dumpops[di]){fprintf(dumpf,"%ld %d %ld ",(long)k,sg,live);long vs=getenv("VAL_SHOT")?atol(getenv("VAL_SHOT")):-1;for(uint32_t q=0;q<nq;q++){if(vs>=0)fputc(((qv(q)[vs>>6]>>(vs&63))&1)?'1':'0',dumpf);else fputc(dirty[q]?'1':'.',dumpf);}fputc('\n',dumpf);di++;}
    if((k&255)==0)for(uint32_t q=840;q<nq;q++)qlive[q]+=dirty[q];
    if(getenv("STATE_OPS")){static vector<long> sops; static bool init=false; if(!init){init=true;string ds=getenv("STATE_OPS");size_t st=0;while(st<ds.size()){size_t e=ds.find(',',st);if(e==string::npos)e=ds.size();sops.push_back(atol(ds.substr(st,e-st).c_str()));st=e+1;}}
      for(long so:sops)if((long)k==so){FILE*sf=fopen((out+"_state_"+to_string(so)+".bin").c_str(),"wb");fwrite(Q.data(),8,Q.size(),sf);fclose(sf);}}
    {static FILE*pl=nullptr; static bool pinit=false; static long inpk=-1; static long PK=0;
     if(!pinit){pinit=true; if(getenv("PEAK_LOG")){pl=fopen(getenv("PEAK_LOG"),"w");PK=atol(getenv("PEAK_LEVEL")?getenv("PEAK_LEVEL"):"892");}}
     if(pl){ if(live>=PK && inpk<0){inpk=k; fprintf(pl,"S %ld ",(long)k); for(uint32_t q=0;q<nq;q++)fputc(dirty[q]?'1':'.',pl); fputc('\n',pl);} 
             else if(live<PK && inpk>=0){fprintf(pl,"E %ld\n",(long)k); inpk=-1;} } }
    wpeak=max(wpeak,live);wpeakws=max(wpeakws,livews);
    if((k+1)%TW==0){tl_peak.push_back(wpeak);tl_peakws.push_back(wpeakws);tl_tof.push_back(wtof/N);wpeak=live;wpeakws=livews;wtof=0;}
  }
  // final checks
  long verr=0,perr=0; 
  vector<u64> bad(W,0);
  for(uint32_t q=0;q<nq;q++){u64*A=qv(q);u64*A0=&Q0[(size_t)q*W];for(int w=0;w<W;w++)bad[w]|=A[w]^A0[w];}
  FILE*ff=fopen((out+"_fails.txt").c_str(),"w");
  for(long sh=0;sh<N;sh++){int w=sh>>6;bool vb=(bad[w]>>(sh&63))&1;bool p=(phase[w]>>(sh&63))&1; if(vb){verr++;fprintf(ff,"%ld value\n",sh);} else if(p!=(bool)ph[sh]){perr++;fprintf(ff,"%ld phase\n",sh);}}
  fclose(ff);
  FILE*o=fopen((out+"_seg.tsv").c_str(),"w");
  fprintf(o,"seg\tops\tstatic_tof\tmean_tof\tmean_hmr\tpeak_live\tpeak_live_ws\tpeak_op\tfirst_op\tlast_op\n");
  for(int i=0;i<nseg;i++)fprintf(o,"%d\t%.0f\t%.0f\t%.4f\t%.4f\t%ld\t%ld\t%ld\t%ld\t%ld\n",i,segops[i],segtofstatic[i],segtof[i]/N,seghmr[i]/N,segpeak[i],segpeakws[i],segpeakop[i],segfirst[i],seglast[i]);
  fclose(o);
  o=fopen((out+"_hist.tsv").c_str(),"w");fprintf(o,"seg\tlevel\tops_at_level\tentries_to_level\n");for(int i=0;i<nseg;i++)for(long L=HL;L<=(long)nq;L++)if(hist[i][L-HL]>0||entries[i][L-HL]>0)fprintf(o,"%d\t%ld\t%.0f\t%ld\n",i,L,hist[i][L-HL],entries[i][L-HL]);fclose(o);
  o=fopen((out+"_timeline.tsv").c_str(),"w");fprintf(o,"window_end_op\tpeak_live\tpeak_live_ws\tmean_tof\n");
  for(size_t i=0;i<tl_peak.size();i++)fprintf(o,"%llu\t%ld\t%ld\t%.4f\n",(unsigned long long)((i+1)*TW),tl_peak[i],tl_peakws[i],tl_tof[i]);fclose(o);
  o=fopen((out+"_peakmap.txt").c_str(),"w");fprintf(o,"peak_live %ld at op %ld\n",gpeak,gpeakop);for(uint32_t q=0;q<nq;q++)fputc(gpeakmap[q]?'1':'.',o);fputc('\n',o);fclose(o);
  fclose(dumpf); if(doCls){FILE*fo=fopen(getenv("CLS_OUT"),"w");for(size_t i=0;i<nqqq;i++)if(fireop[i])fprintf(fo,"%llu %u\n",(unsigned long long)fireop[i],cls[i]);fclose(fo);} if(getenv("FIRE_OUT")){FILE*fo=fopen(getenv("FIRE_OUT"),"w");for(size_t i=0;i<nqqq;i++)if(fireop[i])fprintf(fo,"%llu %u\n",(unsigned long long)fireop[i],fire3[i]);fclose(fo);} {FILE*u=fopen((out+"_qutil.txt").c_str(),"w");for(uint32_t q=840;q<nq;q++)fprintf(u,"%u %.4f\n",q,qlive[q]*256.0/nops);fclose(u);}
  printf("shots %ld mean_toffoli %.4f value_errors %ld phase_errors %ld peak_live %ld at op %ld nq %u\n",N,tottof/N,verr,perr,gpeak,gpeakop,nq);
  return 0;
}
