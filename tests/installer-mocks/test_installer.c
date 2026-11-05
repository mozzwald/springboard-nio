/* Small native OS mock around the unchanged real installer C source. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "../../palm/installer/installer.c"
typedef struct {UInt8 *data;UInt32 size;} Resource;
typedef struct {Resource *image;UInt32 type,creator;UInt16 attrs,opens;int exists;} DB;
static Resource payload[4], resource;
static DB databases[4];
static int locks, creates, deletes, loaded, fail_create;
static UInt16 count(Resource *r){return be16(r->data+76);}
UInt32 MemHandleSize(MemHandle h){return ((Resource *)h)->size;}
void *MemHandleLock(MemHandle h){locks++;return ((Resource *)h)->data;}
void MemHandleUnlock(MemHandle h){(void)h;locks--;}
void DmReleaseResource(MemHandle h){(void)h;}
MemHandle DmGet1Resource(UInt32 type,UInt16 id){assert(type=='nPRC');return id>=1000&&id<1004?&payload[id-1000]:0;}
UInt16 DmNumResources(DmOpenRef p){return count(((DB *)p)->image);}
UInt16 DmFindResource(DmOpenRef p,UInt32 type,UInt16 id,void *unused){
 Resource *r=((DB *)p)->image;UInt16 i;(void)unused;
 for(i=0;i<count(r);i++)if(be32(r->data+78+i*10)==type&&be16(r->data+82+i*10)==id)return i;
 return 0xffff;
}
MemHandle DmGetResourceIndex(DmOpenRef p,UInt16 ix){
 Resource *r=((DB *)p)->image;UInt32 start=be32(r->data+84+ix*10);
 UInt32 end=ix+1<count(r)?be32(r->data+94+ix*10):r->size;
 resource.data=r->data+start;resource.size=end-start;return &resource;
}
LocalID DmFindDatabase(UInt16 card,Char *name){UInt16 i;assert(card==0);for(i=0;i<4;i++)if(databases[i].exists&&!strcmp((char *)databases[i].image->data,name))return i+1;return 0;}
Err DmDatabaseInfo(UInt16 card,LocalID id,Char *name,UInt16 *attr,UInt16 *v,UInt32 *c,UInt32 *m,UInt32 *b,UInt32 *num,LocalID *a,LocalID *s,UInt32 *t,UInt32 *creator){
 DB *d=&databases[id-1];(void)card;(void)name;(void)v;(void)c;(void)m;(void)b;(void)num;(void)a;(void)s;
 *attr=d->attrs;*t=d->type;*creator=d->creator;return 0;
}
Err DmSetDatabaseInfo(UInt16 card,LocalID id,Char *name,UInt16 *attr,UInt16 *v,UInt32 *c,UInt32 *m,UInt32 *b,UInt32 *num,LocalID *a,LocalID *s,UInt32 *t,UInt32 *creator){
 (void)card;(void)name;(void)v;(void)c;(void)m;(void)b;(void)num;(void)a;(void)s;(void)t;(void)creator;
 databases[id-1].attrs=*attr;return 0;
}
DmOpenRef DmOpenDatabase(UInt16 card,LocalID id,UInt16 mode){assert(card==0&&mode==dmModeReadOnly);return &databases[id-1];}
Err DmOpenDatabaseInfo(DmOpenRef p,LocalID *id,UInt16 *open,UInt16 *mode,LocalID *card,Boolean *res){(void)id;(void)mode;(void)card;(void)res;*open=((DB *)p)->opens;return 0;}
Err DmCloseDatabase(DmOpenRef p){(void)p;return 0;}
Err DmDeleteDatabase(UInt16 card,LocalID id){assert(card==0);databases[id-1].exists=0;deletes++;return 0;}
Err DmCreateDatabaseFromImage(void *p){
 UInt16 i;if(fail_create)return 42;
 for(i=0;i<4;i++)if(p==payload[i].data+8){
  static Resource images[4];DB *d=&databases[i];
  images[i].data=p;images[i].size=payload[i].size-8;d->image=&images[i];
  d->type=be32((UInt8 *)p+60);d->creator=be32((UInt8 *)p+64);d->attrs=1;d->opens=1;d->exists=1;creates++;return 0;
 }assert(0);return 1;
}
Err SysLibFind(Char *name,UInt16 *ref){(void)name;(void)ref;return loaded?0:1;}
Err DmGetLastErr(void){return 43;}
int main(int argc,char **argv){
 int i,old;InstallParams params={1,0,0,0,1};assert(argc==5);
 for(i=0;i<4;i++){FILE *f=fopen(argv[i+1],"rb");long n;assert(f);fseek(f,0,SEEK_END);n=ftell(f);rewind(f);payload[i].data=malloc(n);payload[i].size=n;assert(fread(payload[i].data,1,n,f)==(size_t)n);fclose(f);}
 assert(PilotMain(0x8000,&params,0)==0);assert(creates==4&&locks==0);
 /* Idempotent resource comparison skips even a loaded, identical library. */
 loaded=1;assert(PilotMain(0x8000,&params,0)==0);assert(creates==4&&deletes==0&&locks==0);
 /* A different loaded library is never removed. */
 {static Resource different;different=*databases[0].image;different.size--;databases[0].image=&different;
  assert(install_one(0)==BUSY_ERROR);assert(deletes==0&&locks==0);}
 loaded=0;assert(install_one(0)==0);assert(deletes==1&&creates==5&&locks==0);
 /* Foreign same-name metadata and open databases cannot be overwritten. */
 databases[2].creator='XXXX';assert(install_one(2)==INSTALL_ERROR);assert(locks==0);databases[2].creator='NBFI';
 /* Corrupted embedded PRC rejected before any DB mutation. */
 old=creates;payload[1].data[100]^=1;assert(install_one(1)==INSTALL_ERROR);assert(creates==old&&locks==0);payload[1].data[100]^=1;
 /* A create error is returned and retry works; remove leaves RAM apps. */
 databases[3].exists=0;fail_create=1;assert(install_one(3)==42&&locks==0);fail_create=0;assert(install_one(3)==0);
 assert(PilotMain(0x8001,0,0)==0&&databases[3].exists);
 params.setupCardNo=1;assert(PilotMain(0x8000,&params,0)==INSTALL_ERROR);
 for(i=0;i<4;i++)free(payload[i].data);
 puts("installer native policy: PASS (mock OS, not physical installation)");return 0;
}
