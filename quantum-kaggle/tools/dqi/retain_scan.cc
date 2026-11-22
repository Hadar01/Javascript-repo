// Product-retention scan for DQI .kmb circuits (own code; parser/semantics shared with prof.cc).
//
// mode "hash": simulate N official-distribution shots (bit-packed values; phases are not needed for this mode) and,
//   for every Toffoli-like gate, write a record with the 128-bit hash of its executed product plane
//     CCX(a,b->t)   P = cond & a & b            (the value XOR-ed into t)
//     CSWAP(c;x,y)  P = cond & c & (x ^ y)      (the value XOR-ed into x and into y)
//     CCZ(a,b,c)    three records, P = cond & (pair) for the pairs ab, ac, bc  (CCZ -> CZ(f, third) if f holds P)
//   plus hashes of the two factor planes (cond&a, cond&b; for CSWAP cond&c, cond&(x^y)), popcount(P), popcount(cond),
//   the condition-stack depth / per-op condition flag, and the hash + popcount of the third wire's plane BEFORE the op
//   (for CCX: the target; ht == hp1 means the target holds exactly the product, i.e. the gate uncomputes it to 0).
// mode "free": read candidate edges (i, j) (op indices, i < j) and, while simulating, report for each edge the qubits
//   that are untouched by every op in [i, j] and zero on all shots at op j, split into
//     certain-zero: last write was an unconditional R/HMR (empty condition stack, no per-op condition), or never
//                   written and not an input qubit;
//     sample-zero:  zero on every simulated shot (weaker).
//
// usage: retain_scan hash <kmb> <inputs prefix> <N> <out.bin>
//        retain_scan free <kmb> <inputs prefix> <N> <edges.bin> <out.txt>
//        retain_scan check <kmb> <inputs prefix> <N> <cands.txt> <out.txt>
//          cands.txt lines: "F1 k" / "F2 k" (gate k: P == cond&factor1 / factor2), "PP i j s" (P_i == P_j, s = CCZ pair index at j
//          or 0). out: per candidate, the number of shots violating the identity and the number of shots with P != 0.
//        retain_scan profile <kmb> <inputs prefix> <N> <out prefix>   -> <out>_fc.u16, <out>_fs.u16: per op k, the number of
//          certain-zero / sample-zero wires NOT touched by op k (state before op k)
//   edges.bin: pairs of u64 (i, j), any order.
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
template<class T> static vector<T> blob(FILE*f,u64 code,u64 cnt){u64 c=rd64(f);if(c!=code){fprintf(stderr,"bad code\n");exit(1);}u64 sz=rd64(f);if(sz!=cnt*sizeof(T)){fprintf(stderr,"bad size\n");exit(1);}vector<T> v(cnt);if(cnt&&fread(v.data(),sizeof(T),cnt,f)!=cnt){exit(1);}return v;}
struct Reg{string name;vector<uint32_t> ids;};
static u64 s[4];
static inline u64 rotl(u64 x,int k){return (x<<k)|(x>>(64-k));}
static inline u64 rnd(){u64 r=rotl(s[1]*5,7)*9;u64 t=s[1]<<17;s[2]^=s[0];s[3]^=s[1];s[1]^=s[2];s[0]^=s[3];s[2]^=t;s[3]=rotl(s[3],45);return r;}
static inline u64 mix(u64 x){x^=x>>33;x*=0xff51afd7ed558ccdull;x^=x>>33;x*=0xc4ceb9fe1a85ec53ull;x^=x>>33;return x;}
static void hash2(const u64*p,int W,u64&h1,u64&h2){h1=0x243F6A8885A308D3ull;h2=0x13198A2E03707344ull;for(int w=0;w<W;w++){h1=mix(h1^p[w])+w;h2=rotl(h2,23)^mix(p[w]+0x9E3779B97F4A7C15ull*(w+1));}}
#pragma pack(push,1)
struct Rec{u64 k;uint8_t type,sub,depth,opc;uint32_t a,b,c;u64 hp1,hp2,hf1,hf2;uint32_t popP,popC;u64 ht;uint32_t popT,pad;};
#pragma pack(pop)
int main(int argc,char**argv){
  if(argc<6){fprintf(stderr,"usage\n");return 1;}
  string mode=argv[1];const char*kmb=argv[2];string inp=argv[3];long N=atol(argv[4]);
  int W=(N+63)/64; if(N%64){fprintf(stderr,"N must be multiple of 64\n");return 1;}
  FILE*f=fopen(kmb,"rb"); unsigned char magic[16]; if(fread(magic,1,16,f)!=16) return 1;
  uint32_t ver=rd32(f),nq=rd32(f),nb=rd32(f),nreg=rd32(f); if(ver!=2) return 2;
  u64 nops=rd64(f),nqqq=rd64(f),nqq=rd64(f),nq1=rd64(f),nb1=rd64(f),nc=rd64(f),nang=rd64(f),ntag=rd64(f),ntagch=rd64(f);
  (void)nang;(void)ntag;(void)ntagch;
  vector<Reg> regs(nreg);
  for(auto&r:regs){rd64(f);rd64(f);uint32_t nl=rd32(f),rl=rd32(f);r.name.resize(nl);if(fread(&r.name[0],1,nl,f)!=nl)return 3;r.ids.resize(rl);if(fread(r.ids.data(),4,rl,f)!=rl)return 3;}
  if(rd64(f)!=1) return 4; if(rd64(f)!=nops) return 4;
  vector<uint8_t> op(nops); if(fread(op.data(),1,nops,f)!=nops) return 5;
  auto qqq0=blob<uint32_t>(f,2,nqqq),qqq1=blob<uint32_t>(f,3,nqqq),qqq2=blob<uint32_t>(f,4,nqqq);
  auto qq0=blob<uint32_t>(f,5,nqq),qq1=blob<uint32_t>(f,6,nqq),q0=blob<uint32_t>(f,7,nq1);
  auto b0=blob<uint32_t>(f,8,nb1),bc=blob<uint32_t>(f,9,nc);
  fclose(f);
  vector<uint32_t> synq, mbits;
  for(int i=0;i<70;i++){string nm="S"+to_string(i);for(auto&r:regs)if(r.name==nm)for(auto id:r.ids)synq.push_back(id&0x7fffffff);}
  for(int j=0;j<4095;j++){string nm="E"+to_string(j);for(auto&r:regs)if(r.name==nm)for(auto id:r.ids)mbits.push_back(id&0x7fffffff);}
  if(synq.size()!=840||mbits.size()!=49140){fprintf(stderr,"reg size\n");return 7;}
  vector<uint16_t> syn(N*70), mb(N*4095);
  {FILE*g=fopen((inp+".syn").c_str(),"rb");if(fread(syn.data(),2,N*70,g)!=(size_t)N*70)return 8;fclose(g);}
  {FILE*g=fopen((inp+".mbuc").c_str(),"rb");if(fread(mb.data(),2,N*4095,g)!=(size_t)N*4095)return 8;fclose(g);}
  vector<u64> Q((size_t)nq*W,0), B((size_t)nb*W,0);
  auto qv=[&](uint32_t q){return &Q[(size_t)q*W];}; auto bv=[&](uint32_t b){return &B[(size_t)b*W];};
  for(long sh=0;sh<N;sh++){int w=sh>>6;u64 bit=1ull<<(sh&63);
    for(int i=0;i<70;i++){uint16_t v=syn[sh*70+i];for(int k=0;k<12;k++)if((v>>k)&1)qv(synq[i*12+k])[w]|=bit;}
    for(int j=0;j<4095;j++){uint16_t v=mb[sh*4095+j];for(int k=0;k<12;k++)if((v>>k)&1)bv(mbits[j*12+k])[w]|=bit;}}
  s[0]=0x9E3779B97F4A7C15ull^(u64)atoll(getenv("PROF_SEED")?getenv("PROF_SEED"):"0");s[1]=0xD1B54A32D192ED03ull;s[2]=0x8CB92BA72F3D8DD7ull;s[3]=0x1234567ull;
  vector<vector<u64>> cstack; vector<u64> base(W,~0ull), cond(W), P(W), F1(W), F2(W);
  // free-wire tracking
  bool freemode = mode=="free"; bool profmode = mode=="profile"; bool checkmode = mode=="check";
  struct Cand{string kind; u64 i,j; int sub; long viol=0, nz=0, nzi=0;}; vector<Cand> cands; vector<vector<u64>> held;
  if(checkmode){FILE*g=fopen(argv[5],"r"); char kb[8]; unsigned long long a1,a2; int sb; while(fscanf(g,"%7s",kb)==1){Cand c; c.kind=kb; if(c.kind=="PP"){if(fscanf(g,"%llu %llu %d",&a1,&a2,&sb)!=3)break; c.i=a1;c.j=a2;c.sub=sb;} else {if(fscanf(g,"%llu",&a1)!=1)break; c.i=a1;c.j=a1;c.sub=0;} cands.push_back(c);} fclose(g); held.assign(cands.size(),{});}
  vector<vector<size_t>> at_op_dummy;
  vector<uint8_t> zf(nq,0); vector<uint16_t> FC, FS; if(profmode){FC.resize(nops);FS.resize(nops);}
  vector<long long> last_touch(nq,-1); vector<uint8_t> certain(nq,1); for(auto q:synq) certain[q]=0;
  vector<pair<u64,u64>> edges; size_t ei=0; FILE*fo=nullptr;
  if(freemode){FILE*g=fopen(argv[5],"rb");u64 ij[2];while(fread(ij,8,2,g)==2)edges.push_back({ij[1],ij[0]});fclose(g);sort(edges.begin(),edges.end());fo=fopen(argv[6],"w");}
  FILE*ro = (freemode||profmode||checkmode)?nullptr:fopen(argv[5],"wb");
  bool hashmode = !(freemode||profmode||checkmode);
  // candidate lookup by op index
  vector<pair<u64,size_t>> cev; for(size_t z=0;z<cands.size();z++){cev.push_back({cands[z].i,z}); if(cands[z].kind=="PP") cev.push_back({cands[z].j,z});} sort(cev.begin(),cev.end()); size_t cpos=0;
  auto pc=[&](const u64*c){long t=0;for(int w=0;w<W;w++)t+=__builtin_popcountll(c[w]);return t;};
  auto iszero=[&](uint32_t q){const u64*p=qv(q);u64 o=0;for(int w=0;w<W;w++)o|=p[w];return o==0;};
  auto emit=[&](u64 k,uint8_t type,uint8_t sub,uint8_t depth,uint8_t opc,uint32_t a,uint32_t b,uint32_t c,const u64*Pp,const u64*f1,const u64*f2,long popC){
    Rec r; {u64 t2; hash2(qv(c),W,r.ht,t2); r.popT=(uint32_t)pc(qv(c)); r.pad=0;} r.k=k;r.type=type;r.sub=sub;r.depth=depth;r.opc=opc;r.a=a;r.b=b;r.c=c; hash2(Pp,W,r.hp1,r.hp2); u64 t; hash2(f1,W,r.hf1,t); hash2(f2,W,r.hf2,t);
    r.popP=(uint32_t)pc(Pp); r.popC=(uint32_t)popC; fwrite(&r,sizeof r,1,ro);};
  for(uint32_t q=0;q<nq;q++) zf[q]=iszero(q); long nzf=0,ncz=0; for(uint32_t q=0;q<nq;q++){nzf+=zf[q]; ncz+=certain[q]&&zf[q];}
  size_t iqqq=0,iqq=0,iq=0,ib=0,ic=0;
  uint32_t tq[3]; int ntq=0;
  for(u64 k=0;k<nops;k++){
    uint8_t t=op[k];
    bool hasc=(t&0x80)&&t!=0x81;
    memcpy(cond.data(),base.data(),8*W);
    if(hasc){u64*c=bv(bc[ic++]);for(int w=0;w<W;w++)cond[w]&=c[w];}
    bool uncond = cstack.empty() && !hasc;
    uint8_t bt=t&0x7f; int nqt=(t>>4)&3; bool hb=t&0x40; ntq=0;
    // the qubits this op touches (for free-wire tracking; decided before executing)
    if(nqt==3){tq[0]=qqq0[iqqq];tq[1]=qqq1[iqqq];tq[2]=qqq2[iqqq];ntq=3;}
    else if(nqt==2){tq[0]=qq0[iqq];tq[1]=qq1[iqq];ntq=2;}
    else if(nqt==1){tq[0]=q0[iq];ntq=1;}
    long a1=nzf,a2=ncz; if(profmode){for(int z=0;z<ntq;z++){bool dup=false; for(int y=0;y<z;y++) if(tq[y]==tq[z]) dup=true; if(dup) continue; if(zf[tq[z]]) a1--; if(zf[tq[z]]&&certain[tq[z]]) a2--;} FS[k]=(uint16_t)a1; FC[k]=(uint16_t)a2;}
    if(freemode){
      while(ei<edges.size()&&edges[ei].first==k){
        u64 i=edges[ei].second; vector<uint32_t> fc,fs;
        for(uint32_t q=0;q<nq;q++){ if(last_touch[q]>=(long long)i) continue; bool inj=false; for(int z=0;z<ntq;z++) if(tq[z]==q) inj=true; if(inj) continue;
          if(!iszero(q)) continue; fs.push_back(q); if(certain[q]) fc.push_back(q);}
        fprintf(fo,"%llu %llu %zu %zu",(unsigned long long)i,(unsigned long long)k,fc.size(),fs.size());
        for(size_t z=0;z<fc.size()&&z<12;z++)fprintf(fo," c%u",fc[z]); for(size_t z=0;z<fs.size()&&z<12;z++)fprintf(fo," s%u",fs[z]); fputc('\n',fo); ei++;}
    }
    if(t==0x81){u64*c=bv(bc[ic++]);for(int w=0;w<W;w++)base[w]&=c[w];cstack.push_back(base);}
    else if(t==0x01){if(!cstack.empty())cstack.pop_back();if(cstack.empty())std::fill(base.begin(),base.end(),~0ull);else base=cstack.back();}
    else if(bt==0x06||bt==0x07){}
    else if(nqt==3){uint32_t a=qqq0[iqqq],b=qqq1[iqqq],c=qqq2[iqqq];iqqq++;
      u64*A=qv(a),*Bq=qv(b),*C=qv(c); long popC=pc(cond.data()); uint8_t dep=(uint8_t)min<size_t>(cstack.size(),255);
      if(checkmode){ while(cpos<cev.size()&&cev[cpos].first<k) cpos++; size_t cp=cpos; while(cp<cev.size()&&cev[cp].first==k){ Cand&cd=cands[cev[cp].second]; size_t ci=cev[cp].second;
          int ty=(bt&0x0f)==1?1:((bt&0x0f)==0?0:2); auto plane=[&](int sub,vector<u64>&o){o.resize(W); for(int w=0;w<W;w++){u64 v; if(ty==1) v=A[w]&Bq[w]; else if(ty==2) v=A[w]&(Bq[w]^C[w]); else v= sub==0?A[w]&Bq[w]:(sub==1?A[w]&C[w]:Bq[w]&C[w]); o[w]=v&cond[w];}};
          if(cd.kind=="F1"||cd.kind=="F2"){vector<u64> Pp; plane(0,Pp); for(int w=0;w<W;w++){u64 fct = cd.kind=="F1"? (A[w]&cond[w]) : ((ty==2?(Bq[w]^C[w]):Bq[w])&cond[w]); cd.viol+=__builtin_popcountll(Pp[w]^fct); cd.nz+=__builtin_popcountll(Pp[w]);}}
          else if(cd.i==k && held[ci].empty()){plane(0,held[ci]); for(int w=0;w<W;w++) cd.nzi+=__builtin_popcountll(held[ci][w]);}
          else if(cd.j==k){vector<u64> Pp; plane(cd.sub,Pp); for(int w=0;w<W;w++){cd.viol+=__builtin_popcountll(Pp[w]^held[ci][w]); cd.nz+=__builtin_popcountll(Pp[w]);} held[ci].clear(); held[ci].shrink_to_fit();}
          cp++; } }
      if((bt&0x0f)==1){ // CCX
        if(hashmode){for(int w=0;w<W;w++){P[w]=cond[w]&A[w]&Bq[w];F1[w]=cond[w]&A[w];F2[w]=cond[w]&Bq[w];} emit(k,1,0,dep,hasc,a,b,c,P.data(),F1.data(),F2.data(),popC);}
        for(int w=0;w<W;w++)C[w]^=cond[w]&A[w]&Bq[w]; certain[c]=0;}
      else if((bt&0x0f)==0){ // CCZ: values unchanged
        if(hashmode){for(int w=0;w<W;w++){F1[w]=cond[w]&A[w];F2[w]=cond[w]&Bq[w];}
          for(int w=0;w<W;w++)P[w]=cond[w]&A[w]&Bq[w]; emit(k,0,0,dep,hasc,a,b,c,P.data(),F1.data(),F2.data(),popC);
          for(int w=0;w<W;w++){P[w]=cond[w]&A[w]&C[w];F2[w]=cond[w]&C[w];} emit(k,0,1,dep,hasc,a,b,c,P.data(),F1.data(),F2.data(),popC);
          for(int w=0;w<W;w++){P[w]=cond[w]&Bq[w]&C[w];F1[w]=cond[w]&Bq[w];} emit(k,0,2,dep,hasc,a,b,c,P.data(),F1.data(),F2.data(),popC);}}
      else { // CSWAP a; b c
        if(hashmode){for(int w=0;w<W;w++){P[w]=cond[w]&A[w]&(Bq[w]^C[w]);F1[w]=cond[w]&A[w];F2[w]=cond[w]&(Bq[w]^C[w]);} emit(k,2,0,dep,hasc,a,b,c,P.data(),F1.data(),F2.data(),popC);}
        for(int w=0;w<W;w++){u64 x=(Bq[w]^C[w])&A[w]&cond[w];Bq[w]^=x;C[w]^=x;} certain[b]=0;certain[c]=0;}
    } else if(nqt==2){uint32_t a=qq0[iqq],b=qq1[iqq];iqq++;u64*A=qv(a),*Bq=qv(b);
      if((bt&0x0f)==1){for(int w=0;w<W;w++)Bq[w]^=cond[w]&A[w];certain[b]=0;}
      else if((bt&0x0f)==0){}
      else if((bt&0x0f)==2){for(int w=0;w<W;w++){u64 x=(A[w]^Bq[w])&cond[w];A[w]^=x;Bq[w]^=x;}certain[a]=0;certain[b]=0;}
      else {fprintf(stderr,"unk2 %x\n",t);return 9;}
    } else if(nqt==1){uint32_t a=q0[iq++];u64*A=qv(a);
      if(hb){uint32_t bb=b0[ib++];u64*Bb=bv(bb);
        for(int w=0;w<W;w++){u64 r=rnd();u64 bnew=(Bb[w]&~cond[w])|(r&cond[w]);A[w]&=~cond[w];Bb[w]=bnew;} certain[a]=uncond?1:0;
      } else if((bt&0x0f)==0){}
      else if((bt&0x0f)==1){for(int w=0;w<W;w++)A[w]^=cond[w];certain[a]=0;}
      else if((bt&0x0f)==2){for(int w=0;w<W;w++)A[w]&=~cond[w];certain[a]=uncond?1:0;}
      else {fprintf(stderr,"unk1 %x\n",t);return 9;}
    } else if(hb){uint32_t bb=b0[ib++];u64*Bb=bv(bb);int kk=bt&0x0f;
      if(kk==0)for(int w=0;w<W;w++)Bb[w]&=~cond[w]; else if(kk==1)for(int w=0;w<W;w++)Bb[w]|=cond[w]; else if(kk==2)for(int w=0;w<W;w++)Bb[w]^=cond[w];
    } else if(bt==0x00){}
    else {fprintf(stderr,"unk %x\n",t);return 9;}
    for(int z=0;z<ntq;z++) last_touch[tq[z]]=(long long)k;
    if(profmode){ nzf=a1; ncz=a2; for(int z=0;z<ntq;z++){uint32_t q=tq[z]; bool dup=false; for(int y=0;y<z;y++) if(tq[y]==q) dup=true; if(dup) continue; zf[q]=iszero(q); nzf+=zf[q]; ncz+=(zf[q]&&certain[q]);} }
  }
  if(ro)fclose(ro); if(fo)fclose(fo);
  if(checkmode){FILE*g=fopen(argv[6],"w"); for(auto&cd:cands) fprintf(g,"%s %llu %llu %d viol %ld nz %ld nzi %ld\n",cd.kind.c_str(),(unsigned long long)cd.i,(unsigned long long)cd.j,cd.sub,cd.viol,cd.nz,cd.nzi); fclose(g);}
  if(profmode){string o=argv[5]; FILE*g=fopen((o+"_fc.u16").c_str(),"wb"); fwrite(FC.data(),2,nops,g); fclose(g); g=fopen((o+"_fs.u16").c_str(),"wb"); fwrite(FS.data(),2,nops,g); fclose(g);}
  fprintf(stderr,"done ops %llu\n",(unsigned long long)nops);
  return 0;
}
