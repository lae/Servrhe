#
# FLV Extract
# Copyright (C) 2006-2012  J.D. Purcell (moitah@yahoo.com)
# Python port by Gianluigi Tiesi <sherpya@netfarm.it>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#


##################
### flvfile.py ###
##################

import os
from fractions import Fraction

class FLVException(Exception):
    pass

class DummyWriter(object):
    def WriteChunk(self, *args):
        pass
    def Write(self, *args):
        pass
    def Finish(self, *args):
        pass
    def GetPath(self):
        return None

class TAG(object):
    AUDIO   = 8
    VIDEO   = 9
    SCRIPT  = 18

class FLVFile(object):
    __slots__  = [ '_fd', '_inputPath', '_outputDir', '_fileOffset', '_fileLength' ]
    __slots__ += [ '_audioWriter', '_videoWriter', '_timeCodeWriter', '_warnings' ]

    def __init__(self, inputPath):
        self._inputPath = inputPath
        self._outputDir = os.path.abspath(os.path.dirname(inputPath))
        self._fileOffset = 0
        self._fileLength = os.path.getsize(self._inputPath)
        self._audioWriter = self._videoWriter = self._timeCodeWriter = None
        self._warnings = []

        self._fd = open(inputPath, 'rb')

    def SetOutputDirectory(self, outputDir):
        self._outputDir = os.path.abspath(outputDir)

    def Dispose(self):
        self._fd.close()
        self.CloseOutput(None, True)

    def Close(self):
        self.Dispose()

    def AverageFrameRate(self):
        if self._averageFrameRate is None: return 'N/A'
        return '%f (%s)' % (self._averageFrameRate, self._averageFrameRate)

    def TrueFrameRate(self):
        if self._trueFrameRate is None: return 'N/A'
        return '%f (%s)' % (self._trueFrameRate, self._trueFrameRate)

    def Warnings(self):
        return self._warnings

    __slots__ += [ '_outputPathBase', '_overwrite', '_extractAudio', '_extractVideo', '_extractTimeCodes', '_videoTimeStamps' ]
    __slots__ += [ '_averageFrameRate', '_trueFrameRate' ]
    def ExtractStreams(self, extractAudio, extractVideo, extractTimeCodes, overwrite):
        self._outputPathBase = os.path.join(self._outputDir, os.path.splitext(os.path.basename(self._inputPath))[0])
        self._overwrite = overwrite
        self._extractAudio = extractAudio
        self._extractVideo = extractVideo
        self._extractTimeCodes = extractTimeCodes
        self._videoTimeStamps = []

        self._extractedAudio = self._extractedVideo = self._extractedTimeCodes = False

        self.Seek(0)

        if self._fd.read(4) != 'FLV\x01':
            raise FLVException('Not a flv file') 

        if not os.path.isdir(self._outputDir):
            raise FLVException('Output directory doesn\'t exists or not a directory')

        _flags = self.ReadUInt8()
        dataOffset = self.ReadUInt32()

        self.Seek(dataOffset)

        _prevTagSize = self.ReadUInt32()
        while self._fileOffset < self._fileLength:
            if not self.ReadTag(): break
            if (self._fileLength - self._fileOffset) < 4: break
            _prevTagSize = self.ReadUInt32()

        self._averageFrameRate = self.CalculateAverageFrameRate()
        self._trueFrameRate = self.CalculateTrueFrameRate()

        self.CloseOutput(self._averageFrameRate, False)

    def CloseOutput(self, averageFrameRate, disposing):
        if self._videoWriter is not None:
            self._videoWriter.Finish(averageFrameRate if averageFrameRate else Fraction(25, 1))
            if disposing and self._videoWriter.GetPath() is not None:
                os.unlink(self._videoWriter.GetPath())
            self._videoWriter = None

        if self._audioWriter is not None:
            self._audioWriter.Finish()
            if disposing and self._audioWriter.GetPath() is not None:
                os.unlink(self._audioWriter.GetPath())
            self._audioWriter = None

        if self._timeCodeWriter is not None:
            self._timeCodeWriter.Finish()
            if disposing and self._timeCodeWriter.GetPath() is not None:
                os.unlink(self._timeCodeWriter.GetPath())
            self._timeCodeWriter = None

    def GetAudioWriter(self, mediaInfo):
        if mediaInfo.SoundFormat in (AudioTagHeader.MP3, AudioTagHeader.MP3_8k):
            path = self._outputPathBase + '.mp3'
            if not self.CanWriteTo(path): return DummyWriter()
            return MP3Writer(path, self._warnings)
        elif mediaInfo.SoundFormat in (AudioTagHeader.PCM, AudioTagHeader.PCM_LE):
            path = self._outputPathBase + '.wav'
            if not self.CanWriteTo(path): return DummyWriter()
            sampleRate = AudioTagHeader.SoundRates[mediaInfo.SoundRate]
            bits = AudioTagHeader.SoundSizes[mediaInfo.SoundSize]
            chans = AudioTagHeader.SoundTypes[mediaInfo.SoundType]
            if mediaInfo.SoundFormat == AudioTagHeader.PCM:
                self._warnings.append('PCM byte order unspecified, assuming little endian')
            return WAVWriter(path, bits, chans, sampleRate)
        elif mediaInfo.SoundFormat == AudioTagHeader.AAC:
            path = self._outputPathBase + '.aac'
            if not self.CanWriteTo(path): return DummyWriter()
            return AACWriter(path, self._warnings)
        elif mediaInfo.SoundFormat == AudioTagHeader.SPEEX:
            path = self._outputPathBase + '.spx'
            if not self.CanWriteTo(path): return DummyWriter()
            return SpeexWriter(path, self._fileLength & 0xffffffff)
        else:
            self._warnings.append('Unsupported Sound Format %d' % mediaInfo.SoundFormat)
            return DummyWriter()

    def GetVideoWriter(self, mediaInfo):
        if mediaInfo.CodecID in (VideoTagHeader.H263, VideoTagHeader.SCREEN, VideoTagHeader.SCREENv2, VideoTagHeader.VP6, VideoTagHeader.VP6v2):
            path = self._outputPathBase + '.avi'
            if not self.CanWriteTo(path): return DummyWriter()
            return AVIWriter(path, mediaInfo.CodecID, self._warnings)
        elif mediaInfo.CodecID == VideoTagHeader.AVC:
            path = self._outputPathBase + '.264'
            if not self.CanWriteTo(path): return DummyWriter()
            return RawH264Writer(path)
        else:
            self._warnings.append('Unsupported CodecID %d' % mediaInfo.CodecID)
            return DummyWriter()

    __slots__ += [ '_extractedAudio', '_extractedVideo', '_extractedTimeCodes' ]
    def ReadTag(self):
        if (self._fileLength - self._fileOffset) < 11:
            return False

        # 2bit reserved - 1bit filter - 5bit tagtype
        tagType = self.ReadUInt8()
        if tagType & 0xe0:
            raise Exception('Encrypted or invalid packet')

        dataSize = self.ReadUInt24()
        timeStamp = self.ReadUInt24()
        timeStamp |= self.ReadUInt8() << 24
        _StreamID = self.ReadUInt24()   # always 0

        # Read tag data
        if dataSize == 0:
            return True

        if (self._fileLength - self._fileOffset) < dataSize:
            return False

        mediaInfo = self.ReadBytes(1)
        dataSize -= 1

        audioInfo = AudioTagHeader.from_buffer_copy(mediaInfo)
        videoInfo = VideoTagHeader.from_buffer_copy(mediaInfo)

        chunk = bytearray(self.ReadBytes(dataSize))

        if tagType == TAG.AUDIO:
            if self._audioWriter is None:
                if self._extractAudio:
                    self._audioWriter = self.GetAudioWriter(audioInfo)
                    self._extractedAudio = True
                else:
                    self._audioWriter = DummyWriter()
            self._audioWriter.WriteChunk(chunk, timeStamp)

        elif tagType == TAG.VIDEO and (videoInfo.FrameType != 5): # video info/command frame
            if self._videoWriter is None:
                if self._extractVideo:
                    self._videoWriter = self.GetVideoWriter(videoInfo)
                    self._extractedVideo = True
                else:
                    self._videoWriter = DummyWriter()

            if self._timeCodeWriter is None:
                if self._extractTimeCodes:
                    path = self._outputPathBase + '.txt'
                    if self.CanWriteTo(path):
                        self._timeCodeWriter = TimeCodeWriter(path)
                        self._extractedTimeCodes = True
                    else:
                        self._timeCodeWriter = DummyWriter()
                else:
                    self._timeCodeWriter = DummyWriter()

            self._videoTimeStamps.append(timeStamp)
            self._videoWriter.WriteChunk(chunk, timeStamp, videoInfo.FrameType)
            self._timeCodeWriter.Write(timeStamp)

        elif tagType == TAG.SCRIPT:
            pass
        else:
            raise Exception('Unknown tag %d' % tagType)

        return True

    def CanWriteTo(self, path):
        return not os.path.exists(path) or self._overwrite

    def CalculateAverageFrameRate(self):
        frameCount = len(self._videoTimeStamps)
        if frameCount > 1:
            n = (frameCount - 1) * 1000 # TODO: cast uint32_t
            d = self._videoTimeStamps[frameCount - 1] - self._videoTimeStamps[0]
            return Fraction(n, d)
        return None

    def CalculateTrueFrameRate(self):
        deltaCount = {}

        for i in xrange(1, len(self._videoTimeStamps)):
            deltaS = self._videoTimeStamps[i] - self._videoTimeStamps[i - 1]

            if deltaS <= 0: continue
            delta = deltaS

            if delta in deltaCount:
                deltaCount[delta] += 1
            else:
                deltaCount[delta] = 1

        threshold = len(self._videoTimeStamps) / 10
        minDelta = None # let's say None is maxint

        # Find the smallest delta that made up at least 10% of the frames (grouping in delta+1
        # because of rounding, e.g. a NTSC video will have deltas of 33 and 34 ms)
        for (delta, count) in deltaCount.items():
            if (delta + 1) in deltaCount:
                count += deltaCount[delta + 1]
            if (count >= threshold) and ((minDelta is None) or (delta < minDelta)):
                minDelta = delta

        # Calculate the frame rate based on the smallest delta, and delta+1 if present
        if minDelta is not None:
            count = deltaCount[minDelta]
            totalTime = minDelta * count
            totalFrames = count

            if (minDelta + 1) in deltaCount:
                count = deltaCount[minDelta + 1]
                totalTime += (minDelta + 1) * count
                totalFrames += count

            if totalTime != 0:
                return Fraction(totalFrames * 1000, totalTime)

        return None

    def Seek(self, offset):
        self._fd.seek(offset)
        self._fileOffset = offset

    def ReadUInt8(self):
        return ord(self.ReadBytes(1))

    def ReadUInt24(self):
        data = '\x00' + self.ReadBytes(3)
        return BitConverterBE.ToUInt32(data)

    def ReadUInt32(self):
        return BitConverterBE.ToUInt32(self.ReadBytes(4))

    def ReadBytes(self, size):
        self._fileOffset += size
        return self._fd.read(size)


##################
### general.py ###
##################

from os import SEEK_SET
from struct import pack, unpack_from
from ctypes import c_int, c_uint, c_ulong, c_ulonglong

class Writer(object):
    __slots__ = [ '_path', '_fd']
    def __init__(self, path, mode='wb'):
        self._path = path
        self._fd = open(self._path, mode)

    def Write(self, buff, offset=0, size=None):
        if size is None: size = len(buff) - offset
        buff = buff[offset:offset + size]
        assert len(buff) == size
        self._fd.write(buff)

    def WriteFourCC(self, fourCC):
        if len(fourCC) != 4:
            raise Exception('Invalid fourCC length')
        self.Write(fourCC)

    def Seek(self, pos, whence=SEEK_SET):
        self._fd.seek(pos, whence)

    def Close(self):
        self._fd.close()

    def GetPath(self):
        return self._path

class BitHelper(object):
    @staticmethod
    def Read(x, length):
        r = c_int(x.value >> (64 - length))
        x.value <<= length
        return r.value

    @staticmethod
    def ReadB(_bytes, offset, length):
        startByte = offset.value / 8
        endByte = (offset.value + length - 1) / 8
        skipBits = offset.value % 8
        bits = c_ulong()

        for i in xrange(min(endByte - startByte, 7) + 1):
            bits.value |= _bytes[startByte + i] << (56 - (i * 8))

        if skipBits != 0: BitHelper.Read(bits, skipBits)
        offset.value += length
        return BitHelper.Read(bits, length)

    @staticmethod
    def Write(x, length, value):
        mask = c_ulonglong(0xffffffffffffffffL >> (64 - length))
        x.value = (x.value << length) | (value & mask.value)

    @staticmethod
    def CopyBlock(_bytes, offset, length):
        startByte = offset / 8
        endByte = (offset + length - 1) / 8
        shiftA = offset % 8
        shiftB = 8 - shiftA

        dst = bytearray((length + 7) / 8)
        dstsize = len(dst)

        if shiftA == 0:
            dst[0:dstsize] = _bytes[startByte:startByte + dstsize]
        else:
            for i in xrange(endByte - startByte):
                dst[i] = ((_bytes[startByte + i] << shiftA) | (_bytes[startByte + i + 1] >> shiftB)) & 0xff
            if i < dstsize:
                dst[i] = (_bytes[startByte + i] << shiftA) & 0xff

        dst[dstsize - 1] &= 0xff << ((dstsize * 8) - length)

        return dst

class BitConverterBE(object):
    @staticmethod
    def ToUInt16(buff, offset=0):
        return unpack_from('>H', str(buff[offset:offset + 2]))[0]

    @staticmethod
    def FromUInt32(value):
        return pack('>I', value)

    @staticmethod
    def ToUInt32(buff, offset=0):
        return unpack_from('>I', str(buff[offset:offset + 4]))[0]

    @staticmethod
    def FromUInt64(value):
        return pack('>Q', value)

    @staticmethod
    def ToUInt64(buff, offset=0):
        return unpack_from('>Q', str(buff[offset:offset + 8]))[0]


class BitConverterLE(object):
    @staticmethod
    def FromUInt16(value):
        return pack('<H', value)

    @staticmethod
    def FromUInt32(value):
        return pack('<I', value)

    @staticmethod
    def FromInt32(value):
        return pack('<i', value)

    @staticmethod
    def FromUInt64(value):
        return pack('<Q', value)

_lut = {}
def makeTable(i):
    x = c_uint(i << 24)
    for _ in xrange(8):
        if x.value & 0x80000000:
            x.value = (x.value << 1) ^ 0x04c11db7
        else:
            x.value = x.value << 1
    return x.value

_lut = map(makeTable, xrange(256))

class OggCRC(object):
    @staticmethod
    def Calculate(buff, offset, length):
        crc = c_uint()
        for i in xrange(length):
            crc.value = _lut[((crc.value >> 24) ^ buff[offset + i]) & 0xff] ^ (crc.value << 8)
        return crc.value


#########################
### video/__init__.py ###
#########################

from ctypes import BigEndianStructure, c_ubyte

class VideoTagHeader(BigEndianStructure):
    _, _, H263, SCREEN, VP6, VP6v2, SCREENv2, AVC = xrange(8)
    _fields_ = [
                ('FrameType',       c_ubyte, 4),
                ('CodecID',         c_ubyte, 4)
                ]

class VideoWriter(Writer):
    def WriteChunk(self, chunk, timeStamp, frameType):
        raise Exception('interface')
    def Finish(self, averageFrameRate):
        raise Exception('interface')


##############################
### video/rawh264writer.py ###
##############################

class RawH264Writer(VideoWriter):
    __slots__  = [ '_nalLengthSize' ]

    def __init__(self, path):
        super(RawH264Writer, self).__init__(path)
        self._startCode = '\x00\x00\x00\x01'
        self._nalLengthSize = 0

    def WriteChunk(self, chunk, timeStamp=-1, frameType=-1):
        length = len(chunk)
        if length < 4: return

        # Reference: decode_frame from libavcodec's h264.c

        # header
        if chunk[0] == 0:
            if length < 10: return

            offset = 8

            self._nalLengthSize = (chunk[offset] & 0x03) + 1 ; offset += 1
            spsCount = chunk[offset] & 0x1f ; offset += 1
            ppsCount = -1

            while offset <= (length - 2):
                if (spsCount == 0) and (ppsCount == -1):
                    ppsCount = chunk[offset] ; offset += 1
                    continue

                if spsCount > 0: spsCount -= 1
                elif ppsCount > 0: ppsCount -= 1
                else: break

                clen = BitConverterBE.ToUInt16(chunk, offset)
                offset += 2
                if (offset + clen) > length: break
                self.Write(self._startCode)
                self.Write(chunk, offset, clen)
                offset += clen

        # Video Data
        else:
            assert self._nalLengthSize
            offset = 4

            if self._nalLengthSize != 2:
                self._nalLengthSize = 4

            while offset <= (length - self._nalLengthSize):
                if self._nalLengthSize == 2:
                    clen = BitConverterBE.ToUInt16(chunk, offset)
                else:
                    clen = BitConverterBE.ToUInt32(chunk, offset)
                offset += self._nalLengthSize
                if (offset + clen) > length: break
                self.Write(self._startCode)
                self.Write(chunk, offset, clen)
                offset += clen

    def Finish(self, averageFrameRate):
        self.Close()


###############################
### video/timecodewriter.py ###
###############################

class TimeCodeWriter(VideoWriter):
    def __init__(self, path):
        super(TimeCodeWriter, self).__init__(path, 'w')
        super(TimeCodeWriter, self).Write('# timecode format v2\n')

    def Write(self, timeStamp):
        super(TimeCodeWriter, self).Write('%d\n' % timeStamp)

    def Finish(self):
        self.Close()


#########################
### audio/__init__.py ###
#########################

from ctypes import BigEndianStructure, c_ubyte

class AudioTagHeader(BigEndianStructure):
    SoundRates = [ 5512, 11025, 22050, 44100 ]
    SoundSizes = [ 8, 16 ]
    SoundTypes = [ 1 , 2 ]
    PCM, ADPCM, MP3, PCM_LE, NELLY_16k, NELLY_8k, NELLYMOSER, ALAW, ULAW, _, AAC, SPEEX, _, _, MP3_8k, _ = range(16)
    _fields_ = [
                ('SoundFormat',     c_ubyte, 4),
                ('SoundRate',       c_ubyte, 2),
                ('SoundSize',       c_ubyte, 1),
                ('SoundType',       c_ubyte, 1)
                ]

class AudioWriter(Writer):
    def WriteChunk(self, chunk, size):
        raise Exception('interface')
    def Finish(self):
        raise Exception('interface')


##########################
### audio/aacwriter.py ###
##########################

from ctypes import c_ulonglong

class AACWriter(AudioWriter):
    __slots__  = [ '_warnings' ]

    def __init__(self, path, warnings):
        super(AACWriter, self).__init__(path)
        self._warnings = warnings

    __slots__ += [ '_aacProfile', '_sampleRateIndex', '_channelConfig' ]
    def WriteChunk(self, chunk, size=None):
        length = len(chunk)
        if length < 1: return

        # header
        if chunk[0] == 0:
            #if length > 3: return

            bits = c_ulonglong(BitConverterBE.ToUInt16(chunk, 1) << 48)

            # 0: MAIN - 1: LC - 2: SSR - 3: LTP
            self._aacProfile = BitHelper.Read(bits, 5) - 1
            self._sampleRateIndex = BitHelper.Read(bits, 4)
            self._channelConfig = BitHelper.Read(bits, 4)

            if not (0 <= self._aacProfile <= 3):
                raise Exception('Unsupported AAC profile')
            if self._sampleRateIndex > 12:
                raise Exception('Invalid AAC sample rate index')
            if self._channelConfig > 6:
                raise Exception('Invalid AAC channel configuration')

        # data
        else:
            dataSize = length - 1

            bits = c_ulonglong()
            BitHelper.Write(bits, 12, 0xfff)                    # sync -> always 111111111111
            BitHelper.Write(bits,  1, 0)                        # id -> 0: MPEG-4 - 1: MPEG-2
            BitHelper.Write(bits,  2, 0)                        # layer always 00
            BitHelper.Write(bits,  1, 1)                        # protection absent
            BitHelper.Write(bits,  2, self._aacProfile)
            BitHelper.Write(bits,  4, self._sampleRateIndex)
            BitHelper.Write(bits,  1, 0)                        # private bit
            BitHelper.Write(bits,  3, self._channelConfig)
            BitHelper.Write(bits,  1, 0)                        # original/copy
            BitHelper.Write(bits,  1, 0)                        # home
            # ADTS Variable header
            BitHelper.Write(bits,  1, 0)                        # copyright identification bit
            BitHelper.Write(bits,  1, 0)                        # copyright identification start
            BitHelper.Write(bits, 13, 7 + dataSize)             # Length of the frame incl. header
            BitHelper.Write(bits, 11, 0x7ff)                    # ADTS buffer fullness, 0x7ff indicates VBR
            BitHelper.Write(bits,  2, 0)                        # No raw data block in frame

            self.Write(BitConverterBE.FromUInt64(bits.value), 1, 7)
            self.Write(chunk, 1, dataSize)

    def Finish(self):
        self.Close()
