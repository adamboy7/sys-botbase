#include <switch.h>
#define MAX_LINE_LENGTH 344 * 32 * 2
#define MAX_UDP_PAYLOAD 60000
#define UDP_PORT 6000

extern u64 mainLoopSleepTime;
extern bool debugResultCodes;

int setupUDPSocket();
u64 parseStringToInt(char* arg);
s64 parseStringToSignedLong(char* arg);
u8* parseStringToByteBuffer(char* arg, u64* size);
HidNpadButton parseStringToButton(char* arg);
Result capsscCaptureForDebug(void* buffer, size_t buffer_size, u64* size); //big thanks to Behemoth from the Reswitched Discord!
void flashLed(void);
