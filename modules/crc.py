# -*- coding: utf-8 -*-

# 
# CRC-32 forcer
# Copyright (c) 2013 Nayuki Minase
# 
# http://nayuki.eigenstate.org/page/forcing-a-files-crc-to-any-value
# 

import zlib

dependencies = ["commands"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.mask = (1 << 32) - 1
        self.polynomial = 0x104C11DB7L

    def stop(self):
        pass

    def patch(self, filename, crc, offset):
        try:
            assert len(crc) == 8
            desired = int(crc, 16)
            assert desired & self.mask == desired
        except:
            raise self.master.modules["commands"].exception("Invalid desired CRC")

        try:
            file = open(filename, "r+b")
            try:
                file.seek(0, 2)
                length = file.tell()
                file.seek(0, 0)

                if offset < 0 or offset + 4 > length:
                    raise self.master.modules["commands"].exception("Invalid offset")

                crc = self.crc(file)
                new_crc = self.reverse(desired)
                delta = crc ^ new_crc
                patch = self.multiply(self.reciprocal(self.pow(2, (length - offset) * 8)), delta)

                file.seek(offset)
                bytes = bytearray(file.read(4))
                if len(bytes) != 4:
                    raise self.master.modules["commands"].exception("Could not read four bytes at offset")

                for i in range(4):
                    bytes[i] ^= (self.reverse(patch) >> (i * 8)) & 0xFF

                file.seek(offset)
                file.write(bytes)
            except IOError:
                raise self.master.modules["commands"].exception("IO Error")
            finally:
                file.close()
        except IOError:
            raise self.master.modules["commands"].exception("Could not open file")

    def crc(self, file):
        file.seek(0)
        crc = 0
        while True:
            buffer = file.read(128 * 1024)
            if len(buffer) == 0:
                return self.reverse(crc & self.mask)
            else:
                crc = zlib.crc32(buffer, crc)

    def reverse(self, bits):
        rbits = 0
        for i in range(32):
            rbits = (rbits << 1) | (bits & 1)
            bits >>= 1
        return rbits

    # Returns polynomial x multiplied by polynomial y modulo the generator polynomial.
    def multiply(self, x, y):
        # Russian peasant multiplication algorithm
        z = 0
        while y != 0:
            if y & 1 != 0:
                z ^= x
            y >>= 1
            x <<= 1
            if x & (1 << 32) != 0:
                x ^= self.polynomial
        return z

    # Returns polynomial x to the power of natural number y modulo the generator polynomial.
    def pow(self, x, y):
        # Exponentiation by squaring
        z = 1
        while y != 0:
            if y & 1 != 0:
                z = self.multiply(z, x)
            x = self.multiply(x, x)
            y >>= 1
        return z

    # Computes polynomial x divided by polynomial y, returning the quotient and remainder.
    def divide(self, x, y):
        if y == 0:
            raise ValueError("Division by zero")
        if x == 0:
            return (0, 0)
        
        ydeg = self.degree(y)
        z = 0
        for i in range(self.degree(x) - ydeg, -1, -1):
            if (x & (1 << (i + ydeg)) != 0):
                x ^= y << i
                z |= 1 << i
        return (z, x)

    # Returns the reciprocal of polynomial x with respect to the modulus polynomial m.
    def reciprocal(self, x):
        # Based on a simplification of the extended Euclidean algorithm
        y = x
        x = self.polynomial
        a = 0
        b = 1
        while (y != 0):
            divrem = self.divide(x, y)
            c = a ^ self.multiply(divrem[0], b)
            x = y
            y = divrem[1]
            a = b
            b = c
        if x == 1:
            return a
        else:
            raise ValueError("Reciprocal does not exist")

    def degree(self, x):
        if x == 0:
            return -1
        i = 0
        while True:
            if x >> i == 1:
                return i
            i += 1
