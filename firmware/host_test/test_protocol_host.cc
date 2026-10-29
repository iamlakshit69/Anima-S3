#include "protocol_gen.h"
#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    printf("[HOST_TEST] Testing protocol_gen.h header framing and constants...\n");

    // 1. Verify constants
    assert(ANIMA_PROTO_VERSION == 1U);
    assert(ANIMA_HEADER_SIZE == 12U);
    assert(sizeof(AnimaFrameHeader) == 12U);
    assert(ANIMA_KIND_UP == 0x01U);
    assert(ANIMA_KIND_DOWN == 0x02U);
    assert(ANIMA_FLAG_FIRST == 0x01U);
    assert(ANIMA_FLAG_LAST == 0x02U);

    // 2. Test encoding
    uint8_t buf[32];
    memset(buf, 0, sizeof(buf));
    anima_frame_encode(buf, ANIMA_KIND_UP, ANIMA_FLAG_FIRST, 42, 7, 1000);

    // 3. Test decoding
    AnimaFrameHeader hdr;
    memset(&hdr, 0, sizeof(hdr));
    int ok = anima_frame_decode(buf, sizeof(buf), &hdr);
    assert(ok == 1);
    assert(hdr.kind == ANIMA_KIND_UP);
    assert(hdr.flags == ANIMA_FLAG_FIRST);
    assert(hdr.seq == 42);
    assert(hdr.turn == 7);
    assert(hdr.t_ms == 1000);

    // 4. Test invalid kind rejection
    buf[0] = 0x99;
    ok = anima_frame_decode(buf, sizeof(buf), &hdr);
    assert(ok == 0);

    // 5. Test short length rejection
    buf[0] = ANIMA_KIND_UP;
    ok = anima_frame_decode(buf, 11, &hdr);
    assert(ok == 0);

    printf("[HOST_TEST] All protocol host tests passed!\n");
    return 0;
}

