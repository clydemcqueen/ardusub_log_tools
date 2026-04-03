# FMT DataFlash Message
Commit: abe1721cf5

**Purpose**: Defines the format of other messages in the log file. Every message type (except FMT) must have a corresponding FMT message.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **Type** | Message ID (identifier used in packet headers) | |
| **Length** | Total length of the message packet | Bytes |
| **Name** | Name of the message type (e.g., "GPS", "ATT") | char[4] |
| **Format** | Character sequence defining field types (e.g., "Q" for uint64, "f" for float) | char[16] |
| **Labels** | Comma-separated field names | char[64] |
