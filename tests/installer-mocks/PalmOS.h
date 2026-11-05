#ifndef MOCK_PALMOS_H
#define MOCK_PALMOS_H
#include <stdint.h>
#include <string.h>
typedef uint8_t UInt8, Boolean;
typedef uint16_t UInt16, Err;
typedef uint32_t UInt32, LocalID;
typedef char Char;
typedef void *MemPtr, *MemHandle, *DmOpenRef;
#define true 1
#define false 0
#define dmHdrAttrResDB 1
#define dmHdrAttrBackup 8
#define dmModeReadOnly 2
UInt32 MemHandleSize(MemHandle);
void *MemHandleLock(MemHandle);
void MemHandleUnlock(MemHandle);
void DmReleaseResource(MemHandle);
MemHandle DmGet1Resource(UInt32,UInt16);
UInt16 DmNumResources(DmOpenRef);
UInt16 DmFindResource(DmOpenRef,UInt32,UInt16,void *);
MemHandle DmGetResourceIndex(DmOpenRef,UInt16);
LocalID DmFindDatabase(UInt16,Char *);
Err DmDatabaseInfo(UInt16,LocalID,Char *,UInt16 *,UInt16 *,UInt32 *,UInt32 *,UInt32 *,UInt32 *,LocalID *,LocalID *,UInt32 *,UInt32 *);
Err DmSetDatabaseInfo(UInt16,LocalID,Char *,UInt16 *,UInt16 *,UInt32 *,UInt32 *,UInt32 *,UInt32 *,LocalID *,LocalID *,UInt32 *,UInt32 *);
DmOpenRef DmOpenDatabase(UInt16,LocalID,UInt16);
Err DmOpenDatabaseInfo(DmOpenRef,LocalID *,UInt16 *,UInt16 *,LocalID *,Boolean *);
Err DmCloseDatabase(DmOpenRef);
Err DmDeleteDatabase(UInt16,LocalID);
Err DmCreateDatabaseFromImage(void *);
Err SysLibFind(Char *,UInt16 *);
Err DmGetLastErr(void);
#define MemMove memmove
#define MemCmp memcmp
#endif
