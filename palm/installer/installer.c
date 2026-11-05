/* Handspring copies HsSU/HsCd to card 0 and invokes Install (0x8000).
 * Install the complete PRCs into RAM; no retained ROM callbacks/globals.
 * Removal leaves the standalone RAM apps installed. No network operations. */
#include <PalmOS.h>
#include <stddef.h>
typedef struct { UInt16 cardNo; UInt8 isReset, reserved; UInt16 setupCardNo; LocalID setupDbID; } InstallParams;
typedef char params_size[(sizeof(InstallParams)==10)?1:-1];
typedef char params_offset[(offsetof(InstallParams,setupDbID)==6)?1:-1];
#ifdef NIOLIB_M5
#define INSTALL_COUNT 5
#else
#define INSTALL_COUNT 4
#endif
#define INSTALL_ERROR 0x7c01
#define BUSY_ERROR 0x7c02
static UInt32 be32(const UInt8 *p) { return ((UInt32)p[0]<<24)|((UInt32)p[1]<<16)|((UInt32)p[2]<<8)|p[3]; }
static UInt16 be16(const UInt8 *p) { return ((UInt16)p[0]<<8)|p[1]; }
static UInt32 crc32(const UInt8 *p, UInt32 n) {
 UInt32 c=0xffffffffUL; UInt16 b;
 while(n--) { c^=*p++; for(b=0;b<8;b++) c=(c>>1)^((c&1)?0xedb88320UL:0); }
 return ~c;
}
static Boolean same_resources(DmOpenRef db, const UInt8 *p, UInt32 n) {
 UInt16 i,count=be16(p+76); MemHandle h; MemPtr v; UInt32 start,end;
 if(DmNumResources(db)!=count)return false;
 for(i=0;i<count;i++) {
  UInt16 ix=DmFindResource(db,be32(p+78+10*i),be16(p+82+10*i),0);
  if(ix==0xffff)return false;
  start=be32(p+84+10*i);end=i+1<count?be32(p+94+10*i):n;
  if(start>end||end>n)return false;
  h=DmGetResourceIndex(db,ix);if(!h)return false;
  if(MemHandleSize(h)!=end-start){DmReleaseResource(h);return false;}
  v=MemHandleLock(h);if(!v){DmReleaseResource(h);return false;}
  {Boolean equal=MemCmp(v,p+start,end-start)==0;MemHandleUnlock(h);DmReleaseResource(h);if(!equal)return false;}
 }
 return true;
}
static Err install_one(UInt16 index) {
 MemHandle h=DmGet1Resource('nPRC',1000+index); UInt8 *p; UInt32 n,type,creator;
 LocalID id; DmOpenRef db; UInt16 attrs,opens,ref; Err err=INSTALL_ERROR; Char name[32];
 if(!h)return INSTALL_ERROR;
 p=MemHandleLock(h);if(!p){DmReleaseResource(h);return INSTALL_ERROR;}
 if(MemHandleSize(h)<86)goto done;
 n=be32(p);if(n!=MemHandleSize(h)-8||crc32(p+8,n)!=be32(p+4))goto done;
 p+=8;MemMove(name,p,32);name[31]=0;type=be32(p+60);creator=be32(p+64);
 if(!(be16(p+32)&dmHdrAttrResDB)||!be16(p+76)||78UL+10UL*be16(p+76)>n)goto done;
 /* Exact expected identities; never overwrite an unrelated same-name DB. */
 if((index==0&&(type!='libr'||creator!='NiL1'))||
    (index==1&&(type!='appl'||creator!='NiT1'))||
    (index==2&&(type!='appl'||creator!='NBFI'))||
    (index==3&&(type!='appl'||creator!='NBFW'))
#ifdef NIOLIB_M5
    ||(index==4&&(type!='appl'||creator!='NiC1'))
#endif
    )goto done;
 id=DmFindDatabase(0,name);
 if(id) {
  UInt32 oldtype=0,oldcreator=0;
  err=DmDatabaseInfo(0,id,0,&attrs,0,0,0,0,0,0,0,&oldtype,&oldcreator);
  if(err||oldtype!=type||oldcreator!=creator||!(attrs&dmHdrAttrResDB)){err=INSTALL_ERROR;goto done;}
  db=DmOpenDatabase(0,id,dmModeReadOnly);if(!db){err=DmGetLastErr();goto done;}
  err=DmOpenDatabaseInfo(db,0,&opens,0,0,0);
  if(!err&&same_resources(db,p,n)){DmCloseDatabase(db);err=0;goto done;}
  DmCloseDatabase(db);if(err)goto done;
  if(opens>1||(type=='libr'&&SysLibFind(name,&ref)==0)){err=BUSY_ERROR;goto done;}
  err=DmDeleteDatabase(0,id);if(err)goto done;
 }
 /* The database image must be the complete locked chunk, not p==h+8.
  * Palm may inspect its allocation/handle; a desktop PRC payload pointer
  * inside our length/CRC envelope is not an allocated chunk base. */
 {MemHandle image=MemHandleNew(n);MemPtr imageP;
  if(!image){err=memErrNotEnoughSpace;goto done;}
  imageP=MemHandleLock(image);
  if(!imageP){MemHandleFree(image);err=memErrNotEnoughSpace;goto done;}
  MemMove(imageP,p,n);
  err=DmCreateDatabaseFromImage(imageP);
  MemHandleUnlock(image);MemHandleFree(image);
  if(err)goto done;
 }
 id=DmFindDatabase(0,name);if(!id){err=INSTALL_ERROR;goto done;}
 db=DmOpenDatabase(0,id,dmModeReadOnly);if(!db){err=DmGetLastErr();goto done;}
 if(!same_resources(db,p,n))err=INSTALL_ERROR;
 DmCloseDatabase(db);
 if(!err){attrs=dmHdrAttrResDB|dmHdrAttrBackup;err=DmSetDatabaseInfo(0,id,0,&attrs,0,0,0,0,0,0,0,0,0);}
 done: MemHandleUnlock(h);DmReleaseResource(h);return err;
}
UInt32 PilotMain(UInt16 cmd, MemPtr param, UInt16 flags) {
 UInt16 i; Err e; (void)flags;
 if(cmd==0x8001)return 0; /* RAM software survives removal; no retained hooks. */
 if(cmd!=0x8000)return 0;
 {InstallParams *p=(InstallParams *)param;
  if(!p||p->setupCardNo!=0||!p->cardNo)return INSTALL_ERROR;}
 for(i=0;i<INSTALL_COUNT;i++){e=install_one(i);if(e)return (UInt16)e;}
 return 0;
}
