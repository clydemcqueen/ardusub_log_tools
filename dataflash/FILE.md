# FILE DataFlash Message
Commit: cc88f9a550

**Purpose**: Logs file transfer or system file data chunks.
**Location**: `libraries/AP_Logger/LogStructure.h`

Struct:
~~~
struct PACKED log_File {
    LOG_PACKET_HEADER;
    char filename[16];
    uint32_t offset;
    uint8_t length;
    char data[64];
};
~~~

Comments:
~~~
// @LoggerMessage: FILE
// @Description: File data
// @Field: FileName: File name
// @Field: Offset: Offset into the file of this block
// @Field: Length: Length of this data block
// @Field: Data: File data of this block
~~~

Formatting and field names:
~~~
    { LOG_FILE_MSG, sizeof(log_File), \
      "FILE",   "NIBZ",       "FileName,Offset,Length,Data", "----", "----" }, \
~~~
