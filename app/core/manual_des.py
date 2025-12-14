import struct

class DESHelper:
    ENCRYPT = 1
    DECRYPT = 0
    
    # S-Boxes
    sbox1 = [
        14,  4,  13,  1,   2, 15,  11,  8,   3, 10,   6, 12,   5,  9,   0,  7,
         0, 15,   7,  4,  14,  2,  13,  1,  10,  6,  12, 11,   9,  5,   3,  8,
         4,  1,  14,  8,  13,  6,   2, 11,  15, 12,   9,  7,   3, 10,   5,  0,
        15, 12,   8,  2,   4,  9,   1,  7,   5, 11,   3, 14,  10,  0,   6, 13
    ]
    sbox2 = [
        15,  1,   8, 14,   6, 11,   3,  4,   9,  7,   2, 13,  12,  0,   5, 10,
         3, 13,   4,  7,  15,  2,   8, 15,  12,  0,   1, 10,   6,  9,  11,  5,
         0, 14,   7, 11,  10,  4,  13,  1,   5,  8,  12,  6,   9,  3,   2, 15,
        13,  8,  10,  1,   3, 15,   4,  2,  11,  6,   7, 12,   0,  5,  14,  9
    ]
    sbox3 = [
        10,  0,   9, 14,   6,  3,  15,  5,   1, 13,  12,  7,  11,  4,   2,  8,
        13,  7,   0,  9,   3,  4,   6, 10,   2,  8,   5, 14,  12, 11,  15,  1,
        13,  6,   4,  9,   8, 15,   3,  0,  11,  1,   2, 12,   5, 10,  14,  7,
         1, 10,  13,  0,   6,  9,   8,  7,   4, 15,  14,  3,  11,  5,   2, 12
    ]
    sbox4 = [
         7, 13,  14,  3,   0,  6,   9, 10,   1,  2,   8,  5,  11, 12,   4, 15,
        13,  8,  11,  5,   6, 15,   0,  3,   4,  7,   2, 12,   1, 10,  14,  9,
        10,  6,   9,  0,  12, 11,   7, 13,  15,  1,   3, 14,   5,  2,   8,  4,
         3, 15,   0,  6,  10, 10,  13,  8,   9,  4,   5, 11,  12,  7,   2, 14
    ]
    sbox5 = [
         2, 12,   4,  1,   7, 10,  11,  6,   8,  5,   3, 15,  13,  0,  14,  9,
        14, 11,   2, 12,   4,  7,  13,  1,   5,  0,  15, 10,   3,  9,   8,  6,
         4,  2,   1, 11,  10, 13,   7,  8,  15,  9,  12,  5,   6,  3,   0, 14,
        11,  8,  12,  7,   1, 14,   2, 13,   6, 15,   0,  9,  10,  4,   5,  3
    ]
    sbox6 = [
        12,  1,  10, 15,   9,  2,   6,  8,   0, 13,   3,  4,  14,  7,   5, 11,
        10, 15,   4,  2,   7, 12,   9,  5,   6,  1,  13, 14,   0, 11,   3,  8,
         9, 14,  15,  5,   2,  8,  12,  3,   7,  0,   4, 10,   1, 13,  11,  6,
         4,  3,   2, 12,   9,  5,  15, 10,  11, 14,   1,  7,   6,  0,   8, 13
    ]
    sbox7 = [
         4, 11,   2, 14,  15,  0,   8, 13,   3, 12,   9,  7,   5, 10,   6,  1,
        13,  0,  11,  7,   4,  9,   1, 10,  14,  3,   5, 12,   2, 15,   8,  6,
         1,  4,  11, 13,  12,  3,   7, 14,  10, 15,   6,  8,   0,  5,   9,  2,
         6, 11,  13,  8,   1,  4,  10,  7,   9,  5,   0, 15,  14,  2,   3, 12
    ]
    sbox8 = [
        13,  2,   8,  4,   6, 15,  11,  1,  10,  9,   3, 14,   5,  0,  12,  7,
         1, 15,  13,  8,  10,  3,   7,  4,  12,  5,   6, 11,   0, 14,   9,  2,
         7, 11,   4,  1,   9, 12,  14,  2,   0,  6,  10, 13,  15,  3,   5,  8,
         2,  1,  14,  7,   4, 10,   8, 13,  15, 12,   9,  0,   3,  5,   6, 11
    ]

    @staticmethod
    def _BITNUM(a, b, c):
        # a is byte array
        # b is bit position in 32-bit LE word view?
        # a[(b) / 32 * 4 + 3 - (b) % 32 / 8] 
        # C#: (b) / 32 * 4 is start of 4-byte block
        # 3 - (b % 32 / 8) is byte offset reversed: 3, 2, 1, 0
        idx = (b // 32) * 4 + 3 - (b % 32 // 8)
        byte_val = a[idx]
        bit_val = (byte_val >> (7 - (b % 8))) & 0x01
        return bit_val << c

    @staticmethod
    def _BITNUMINTR(a, b, c):
        # a is uint
        return (((a >> (31 - b)) & 0x00000001) << c)

    @staticmethod
    def _BITNUMINTL(a, b, c):
        # a is uint
        return ((a << b) & 0x80000000) >> c

    @staticmethod
    def _SBOXBIT(a):
        # a is byte
        return ((a & 0x20) | ((a & 0x1f) >> 1) | ((a & 0x01) << 4)) & 0xFFFFFFFF

    @staticmethod
    def KeySchedule(key, schedule, mode):
        # key is byte array, schedule is list of lists
        key_rnd_shift = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]
        key_perm_c = [56, 48, 40, 32, 24, 16, 8, 0, 57, 49, 41, 33, 25, 17,
            9,1,58,50,42,34,26,18,10,2,59,51,43,35]
        key_perm_d = [62,54,46,38,30,22,14,6,61,53,45,37,29,21,
            13,5,60,52,44,36,28,20,12,4,27,19,11,3]
        key_compression = [13,16,10,23,0,4,2,27,14,5,20,9,
            22,18,11,3,25,7,15,6,26,19,12,1,
            40,51,30,36,46,54,29,39,50,44,32,47,
            43,48,38,55,33,52,45,41,49,35,28,31]

        C = 0
        j = 31
        for i in range(28):
            C |= DESHelper._BITNUM(key, key_perm_c[i], j)
            j -= 1
        
        D = 0
        j = 31
        for i in range(28):
            D |= DESHelper._BITNUM(key, key_perm_d[i], j)
            j -= 1

        for i in range(16):
            # Rotate left
            C = ((C << key_rnd_shift[i]) | (C >> (28 - key_rnd_shift[i]))) & 0xfffffff0
            D = ((D << key_rnd_shift[i]) | (D >> (28 - key_rnd_shift[i]))) & 0xfffffff0

            if mode == DESHelper.DECRYPT:
                toGen = 15 - i
            else:
                toGen = i

            schedule[toGen] = [0] * 6 # reset
            
            for j in range(24):
                schedule[toGen][j // 8] |= DESHelper._BITNUMINTR(C, key_compression[j], 7 - (j % 8))
            
            for j in range(24, 48):
                schedule[toGen][j // 8] |= DESHelper._BITNUMINTR(D, key_compression[j] - 27, 7 - (j % 8))

    @staticmethod
    def IP(state, input_bytes):
        # state is uint list [0, 1]
        # input is byte array
        
        # Manually unrolled 64 loops?
        # Reference uses unrolled logic.
        # I'll implement loop for compactness or just copy logic.
        # It sets specific bits.
        
        s0 = 0
        s0 |= DESHelper._BITNUM(input_bytes, 57, 31) | DESHelper._BITNUM(input_bytes, 49, 30) | DESHelper._BITNUM(input_bytes, 41, 29) | DESHelper._BITNUM(input_bytes, 33, 28)
        s0 |= DESHelper._BITNUM(input_bytes, 25, 27) | DESHelper._BITNUM(input_bytes, 17, 26) | DESHelper._BITNUM(input_bytes, 9, 25) | DESHelper._BITNUM(input_bytes, 1, 24)
        s0 |= DESHelper._BITNUM(input_bytes, 59, 23) | DESHelper._BITNUM(input_bytes, 51, 22) | DESHelper._BITNUM(input_bytes, 43, 21) | DESHelper._BITNUM(input_bytes, 35, 20)
        s0 |= DESHelper._BITNUM(input_bytes, 27, 19) | DESHelper._BITNUM(input_bytes, 19, 18) | DESHelper._BITNUM(input_bytes, 11, 17) | DESHelper._BITNUM(input_bytes, 3, 16)
        s0 |= DESHelper._BITNUM(input_bytes, 61, 15) | DESHelper._BITNUM(input_bytes, 53, 14) | DESHelper._BITNUM(input_bytes, 45, 13) | DESHelper._BITNUM(input_bytes, 37, 12)
        s0 |= DESHelper._BITNUM(input_bytes, 29, 11) | DESHelper._BITNUM(input_bytes, 21, 10) | DESHelper._BITNUM(input_bytes, 13, 9) | DESHelper._BITNUM(input_bytes, 5, 8)
        s0 |= DESHelper._BITNUM(input_bytes, 63, 7) | DESHelper._BITNUM(input_bytes, 55, 6) | DESHelper._BITNUM(input_bytes, 47, 5) | DESHelper._BITNUM(input_bytes, 39, 4)
        s0 |= DESHelper._BITNUM(input_bytes, 31, 3) | DESHelper._BITNUM(input_bytes, 23, 2) | DESHelper._BITNUM(input_bytes, 15, 1) | DESHelper._BITNUM(input_bytes, 7, 0)
        state[0] = s0 & 0xFFFFFFFF

        s1 = 0
        s1 |= DESHelper._BITNUM(input_bytes, 56, 31) | DESHelper._BITNUM(input_bytes, 48, 30) | DESHelper._BITNUM(input_bytes, 40, 29) | DESHelper._BITNUM(input_bytes, 32, 28)
        s1 |= DESHelper._BITNUM(input_bytes, 24, 27) | DESHelper._BITNUM(input_bytes, 16, 26) | DESHelper._BITNUM(input_bytes, 8, 25) | DESHelper._BITNUM(input_bytes, 0, 24)
        s1 |= DESHelper._BITNUM(input_bytes, 58, 23) | DESHelper._BITNUM(input_bytes, 50, 22) | DESHelper._BITNUM(input_bytes, 42, 21) | DESHelper._BITNUM(input_bytes, 34, 20)
        s1 |= DESHelper._BITNUM(input_bytes, 26, 19) | DESHelper._BITNUM(input_bytes, 18, 18) | DESHelper._BITNUM(input_bytes, 10, 17) | DESHelper._BITNUM(input_bytes, 2, 16)
        s1 |= DESHelper._BITNUM(input_bytes, 60, 15) | DESHelper._BITNUM(input_bytes, 52, 14) | DESHelper._BITNUM(input_bytes, 44, 13) | DESHelper._BITNUM(input_bytes, 36, 12)
        s1 |= DESHelper._BITNUM(input_bytes, 28, 11) | DESHelper._BITNUM(input_bytes, 20, 10) | DESHelper._BITNUM(input_bytes, 12, 9) | DESHelper._BITNUM(input_bytes, 4, 8)
        s1 |= DESHelper._BITNUM(input_bytes, 62, 7) | DESHelper._BITNUM(input_bytes, 54, 6) | DESHelper._BITNUM(input_bytes, 46, 5) | DESHelper._BITNUM(input_bytes, 38, 4)
        s1 |= DESHelper._BITNUM(input_bytes, 30, 3) | DESHelper._BITNUM(input_bytes, 22, 2) | DESHelper._BITNUM(input_bytes, 14, 1) | DESHelper._BITNUM(input_bytes, 6, 0)
        state[1] = s1 & 0xFFFFFFFF

    @staticmethod
    def InvIP(state, output_bytes):
        # output_bytes is bytearray (modified in place)
        # 3,2,1,0 order for output assignment?
        # Reference: input[3] = ...
        
        output_bytes[3] = (DESHelper._BITNUMINTR(state[1], 7, 7) | DESHelper._BITNUMINTR(state[0], 7, 6) | DESHelper._BITNUMINTR(state[1], 15, 5) | \
            DESHelper._BITNUMINTR(state[0], 15, 4) | DESHelper._BITNUMINTR(state[1], 23, 3) | DESHelper._BITNUMINTR(state[0], 23, 2) | \
            DESHelper._BITNUMINTR(state[1], 31, 1) | DESHelper._BITNUMINTR(state[0], 31, 0)) & 0xFF

        output_bytes[2] = (DESHelper._BITNUMINTR(state[1], 6, 7) | DESHelper._BITNUMINTR(state[0], 6, 6) | DESHelper._BITNUMINTR(state[1], 14, 5) | \
            DESHelper._BITNUMINTR(state[0], 14, 4) | DESHelper._BITNUMINTR(state[1], 22, 3) | DESHelper._BITNUMINTR(state[0], 22, 2) | \
            DESHelper._BITNUMINTR(state[1], 30, 1) | DESHelper._BITNUMINTR(state[0], 30, 0)) & 0xFF

        output_bytes[1] = (DESHelper._BITNUMINTR(state[1], 5, 7) | DESHelper._BITNUMINTR(state[0], 5, 6) | DESHelper._BITNUMINTR(state[1], 13, 5) | \
            DESHelper._BITNUMINTR(state[0], 13, 4) | DESHelper._BITNUMINTR(state[1], 21, 3) | DESHelper._BITNUMINTR(state[0], 21, 2) | \
            DESHelper._BITNUMINTR(state[1], 29, 1) | DESHelper._BITNUMINTR(state[0], 29, 0)) & 0xFF

        output_bytes[0] = (DESHelper._BITNUMINTR(state[1], 4, 7) | DESHelper._BITNUMINTR(state[0], 4, 6) | DESHelper._BITNUMINTR(state[1], 12, 5) | \
            DESHelper._BITNUMINTR(state[0], 12, 4) | DESHelper._BITNUMINTR(state[1], 20, 3) | DESHelper._BITNUMINTR(state[0], 20, 2) | \
            DESHelper._BITNUMINTR(state[1], 28, 1) | DESHelper._BITNUMINTR(state[0], 28, 0)) & 0xFF

        output_bytes[7] = (DESHelper._BITNUMINTR(state[1], 3, 7) | DESHelper._BITNUMINTR(state[0], 3, 6) | DESHelper._BITNUMINTR(state[1], 11, 5) | \
            DESHelper._BITNUMINTR(state[0], 11, 4) | DESHelper._BITNUMINTR(state[1], 19, 3) | DESHelper._BITNUMINTR(state[0], 19, 2) | \
            DESHelper._BITNUMINTR(state[1], 27, 1) | DESHelper._BITNUMINTR(state[0], 27, 0)) & 0xFF

        output_bytes[6] = (DESHelper._BITNUMINTR(state[1], 2, 7) | DESHelper._BITNUMINTR(state[0], 2, 6) | DESHelper._BITNUMINTR(state[1], 10, 5) | \
            DESHelper._BITNUMINTR(state[0], 10, 4) | DESHelper._BITNUMINTR(state[1], 18, 3) | DESHelper._BITNUMINTR(state[0], 18, 2) | \
            DESHelper._BITNUMINTR(state[1], 26, 1) | DESHelper._BITNUMINTR(state[0], 26, 0)) & 0xFF

        output_bytes[5] = (DESHelper._BITNUMINTR(state[1], 1, 7) | DESHelper._BITNUMINTR(state[0], 1, 6) | DESHelper._BITNUMINTR(state[1], 9, 5) | \
            DESHelper._BITNUMINTR(state[0], 9, 4) | DESHelper._BITNUMINTR(state[1], 17, 3) | DESHelper._BITNUMINTR(state[0], 17, 2) | \
            DESHelper._BITNUMINTR(state[1], 25, 1) | DESHelper._BITNUMINTR(state[0], 25, 0)) & 0xFF

        output_bytes[4] = (DESHelper._BITNUMINTR(state[1], 0, 7) | DESHelper._BITNUMINTR(state[0], 0, 6) | DESHelper._BITNUMINTR(state[1], 8, 5) | \
            DESHelper._BITNUMINTR(state[0], 8, 4) | DESHelper._BITNUMINTR(state[1], 16, 3) | DESHelper._BITNUMINTR(state[0], 16, 2) | \
            DESHelper._BITNUMINTR(state[1], 24, 1) | DESHelper._BITNUMINTR(state[0], 24, 0)) & 0xFF

    @staticmethod
    def F(state, key):
        # state uint, key byte array (6 bytes)
        # returns uint
        t1 = 0
        t2 = 0
        
        t1 = DESHelper._BITNUMINTL(state, 31, 0) | ((state & 0xf0000000) >> 1) | DESHelper._BITNUMINTL(state, 4, 5) | \
            DESHelper._BITNUMINTL(state, 3, 6) | ((state & 0x0f000000) >> 3) | DESHelper._BITNUMINTL(state, 8, 11) | \
            DESHelper._BITNUMINTL(state, 7, 12) | ((state & 0x00f00000) >> 5) | DESHelper._BITNUMINTL(state, 12, 17) | \
            DESHelper._BITNUMINTL(state, 11, 18) | ((state & 0x000f0000) >> 7) | DESHelper._BITNUMINTL(state, 16, 23)
        t1 &= 0xFFFFFFFF
        
        t2 = DESHelper._BITNUMINTL(state, 15, 0) | ((state & 0x0000f000) << 15) | DESHelper._BITNUMINTL(state, 20, 5) | \
            DESHelper._BITNUMINTL(state, 19, 6) | ((state & 0x00000f00) << 13) | DESHelper._BITNUMINTL(state, 24, 11) | \
            DESHelper._BITNUMINTL(state, 23, 12) | ((state & 0x000000f0) << 11) | DESHelper._BITNUMINTL(state, 28, 17) | \
            DESHelper._BITNUMINTL(state, 27, 18) | ((state & 0x0000000f) << 9) | DESHelper._BITNUMINTL(state, 0, 23)
        t2 &= 0xFFFFFFFF

        lrgstate = [0] * 6
        lrgstate[0] = (t1 >> 24) & 0xff
        lrgstate[1] = (t1 >> 16) & 0xff
        lrgstate[2] = (t1 >> 8) & 0xff
        lrgstate[3] = (t2 >> 24) & 0xff
        lrgstate[4] = (t2 >> 16) & 0xff
        lrgstate[5] = (t2 >> 8) & 0xff

        for i in range(6):
            lrgstate[i] ^= key[i]

        state = (DESHelper.sbox1[DESHelper._SBOXBIT(lrgstate[0] >> 2)] << 28) | \
            (DESHelper.sbox2[DESHelper._SBOXBIT(((lrgstate[0] & 0x03) << 4) | (lrgstate[1] >> 4))] << 24) | \
            (DESHelper.sbox3[DESHelper._SBOXBIT(((lrgstate[1] & 0x0f) << 2) | (lrgstate[2] >> 6))] << 20) | \
            (DESHelper.sbox4[DESHelper._SBOXBIT(lrgstate[2] & 0x3f)] << 16) | \
            (DESHelper.sbox5[DESHelper._SBOXBIT(lrgstate[3] >> 2)] << 12) | \
            (DESHelper.sbox6[DESHelper._SBOXBIT(((lrgstate[3] & 0x03) << 4) | (lrgstate[4] >> 4))] << 8) | \
            (DESHelper.sbox7[DESHelper._SBOXBIT(((lrgstate[4] & 0x0f) << 2) | (lrgstate[5] >> 6))] << 4) | \
             DESHelper.sbox8[DESHelper._SBOXBIT(lrgstate[5] & 0x3f)]
        state &= 0xFFFFFFFF

        state = DESHelper._BITNUMINTL(state, 15, 0) | DESHelper._BITNUMINTL(state, 6, 1) | DESHelper._BITNUMINTL(state, 19, 2) | \
            DESHelper._BITNUMINTL(state, 20, 3) | DESHelper._BITNUMINTL(state, 28, 4) | DESHelper._BITNUMINTL(state, 11, 5) | \
            DESHelper._BITNUMINTL(state, 27, 6) | DESHelper._BITNUMINTL(state, 16, 7) | DESHelper._BITNUMINTL(state, 0, 8) | \
            DESHelper._BITNUMINTL(state, 14, 9) | DESHelper._BITNUMINTL(state, 22, 10) | DESHelper._BITNUMINTL(state, 25, 11) | \
            DESHelper._BITNUMINTL(state, 4, 12) | DESHelper._BITNUMINTL(state, 17, 13) | DESHelper._BITNUMINTL(state, 30, 14) | \
            DESHelper._BITNUMINTL(state, 9, 15) | DESHelper._BITNUMINTL(state, 1, 16) | DESHelper._BITNUMINTL(state, 7, 17) | \
            DESHelper._BITNUMINTL(state, 23, 18) | DESHelper._BITNUMINTL(state, 13, 19) | DESHelper._BITNUMINTL(state, 31, 20) | \
            DESHelper._BITNUMINTL(state, 26, 21) | DESHelper._BITNUMINTL(state, 2, 22) | DESHelper._BITNUMINTL(state, 8, 23) | \
            DESHelper._BITNUMINTL(state, 18, 24) | DESHelper._BITNUMINTL(state, 12, 25) | DESHelper._BITNUMINTL(state, 29, 26) | \
            DESHelper._BITNUMINTL(state, 5, 27) | DESHelper._BITNUMINTL(state, 21, 28) | DESHelper._BITNUMINTL(state, 10, 29) | \
            DESHelper._BITNUMINTL(state, 3, 30) | DESHelper._BITNUMINTL(state, 24, 31)
        
        return state & 0xFFFFFFFF

    @staticmethod
    def Crypt(input_bytes, key_schedule):
        # input_bytes bytes
        # returns bytes (8)
        state = [0, 0]
        DESHelper.IP(state, input_bytes)
        
        for idx in range(15):
            t = state[1]
            state[1] = (DESHelper.F(state[1], key_schedule[idx]) ^ state[0]) & 0xFFFFFFFF
            state[0] = t
        
        state[0] = (DESHelper.F(state[1], key_schedule[15]) ^ state[0]) & 0xFFFFFFFF
        
        output = bytearray(8)
        DESHelper.InvIP(state, output)
        return bytes(output)

    @staticmethod
    def TripleDESKeySetup(key, schedule, mode):
        # key 24 bytes, schedule 3x16x6 (implemented as list of list of lists)
        # schedule: list[3][16][6] (though in python list of list of list)
        if mode == DESHelper.ENCRYPT:
            DESHelper.KeySchedule(key[0:8], schedule[0], mode)
            DESHelper.KeySchedule(key[8:16], schedule[1], DESHelper.DECRYPT)
            DESHelper.KeySchedule(key[16:24], schedule[2], mode)
        else:
            DESHelper.KeySchedule(key[0:8], schedule[2], mode)
            DESHelper.KeySchedule(key[8:16], schedule[1], DESHelper.ENCRYPT)
            DESHelper.KeySchedule(key[16:24], schedule[0], mode)

    @staticmethod
    def TripleDESCrypt(input_bytes, key_schedules):
        # input_bytes 8 bytes
        # key_schedules 3x16x6
        # returns 8 bytes
        out = DESHelper.Crypt(input_bytes, key_schedules[0])
        out = DESHelper.Crypt(out, key_schedules[1])
        out = DESHelper.Crypt(out, key_schedules[2])
        return out
