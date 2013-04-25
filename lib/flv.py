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


##########################
### video/aviwriter.py ###
##########################

from ctypes import BigEndianStructure, c_uint, c_ulonglong
from os import SEEK_CUR

class H263FrameHeader(BigEndianStructure):
    _fields_ = [
                  ('header',                c_uint, 17),
                  ('picformat',             c_uint, 5),
                  ('ts',                    c_uint, 8),
                  ('format',                c_uint, 3)
                ]

class FLASHSVFrameHeader(BigEndianStructure):
    _fields_ = [
                  ('blockWidth',            c_uint, 4),
                  ('imageWidth',            c_uint, 12),
                  ('blockHeight',           c_uint, 4),
                  ('imageHeight',           c_uint, 12)
                ]

class VP6FrameHeader(BigEndianStructure):
    _fields_ = [
                  ('deltaFrameFlag',        c_uint, 1),
                  ('quant',                 c_uint, 6),
                  ('separatedCoeffFlag',    c_uint, 1),
                  ('subVersion',            c_uint, 5),
                  ('filterHeader',          c_uint, 2),
                  ('interlacedFlag',        c_uint, 1)
                  ]

class VideoFormat(object):
    CIF     = (352, 288)
    QCIF    = (176, 144)
    SQCIF   = (128, 96)
    QVGA    = (320, 240)
    QQVGA   = (160, 120)

class AVIWriter(VideoWriter):
    __slots__  = [ '_codecID', '_warnings', '_isAlphaWriter', '_alphaWriter' ]
    __slots__ += [ '_width', '_height', '_frameCount' ]
    __slots__ += [ '_index', '_moviDataSize' ]

    # Chunk:          Off:  Len:
    #
    # RIFF AVI          0    12
    #   LIST hdrl      12    12
    #     avih         24    64
    #     LIST strl    88    12
    #       strh      100    64
    #       strf      164    48
    #   LIST movi     212    12
    #     (frames)    224   ???
    #   idx1          ???   ???

    def CodecFourCC(self):
        if self._codecID == VideoTagHeader.H263:
            return 'FLV1'
        elif self._codecID in (VideoTagHeader.VP6, VideoTagHeader.VP6v2):
            return 'VP6F'
        elif self._codecID in (VideoTagHeader.SCREEN, VideoTagHeader.SCREENv2): # FIXME: v2?
            return 'FSV1'

    def __init__(self, path, codecID, warnings, isAlphaWriter=False):
        super(AVIWriter, self).__init__(path)
        self._codecID = codecID
        self._isAlphaWriter = isAlphaWriter
        self._alphaWriter = None
        self._warnings = warnings

        self._width = self._height = self._frameCount = 0
        self._index = []
        self._moviDataSize = 0

        if codecID not in (VideoTagHeader.H263, VideoTagHeader.SCREEN, VideoTagHeader.SCREENv2, VideoTagHeader.VP6, VideoTagHeader.VP6v2):
            raise Exception('Unsupported video codec')

        if (codecID == VideoTagHeader.VP6v2) and not isAlphaWriter:
            self._alphaWriter = AVIWriter(path[:-4] + 'alpha.avi', codecID, warnings, True)

        self.WriteFourCC('RIFF')
        self.Write(BitConverterLE.FromUInt32(0)) # chunk size
        self.WriteFourCC('AVI ')

        self.WriteFourCC('LIST')
        self.Write(BitConverterLE.FromUInt32(192))
        self.WriteFourCC('hdrl')

        self.WriteFourCC('avih')
        self.Write(BitConverterLE.FromUInt32(56))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0x10))
        self.Write(BitConverterLE.FromUInt32(0)) # frame count
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(1))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0)) # width
        self.Write(BitConverterLE.FromUInt32(0)) # height
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))

        self.WriteFourCC('LIST')
        self.Write(BitConverterLE.FromUInt32(116))
        self.WriteFourCC('strl')

        self.WriteFourCC('strh')
        self.Write(BitConverterLE.FromUInt32(56))
        self.WriteFourCC('vids')
        self.WriteFourCC(self.CodecFourCC())
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0)) # frame rate denominator
        self.Write(BitConverterLE.FromUInt32(0)) # frame rate numerator
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0)) # frame count
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromInt32(-1))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt16(0))
        self.Write(BitConverterLE.FromUInt16(0))
        self.Write(BitConverterLE.FromUInt16(0)) # width
        self.Write(BitConverterLE.FromUInt16(0)) # height

        self.WriteFourCC('strf')
        self.Write(BitConverterLE.FromUInt32(40))
        self.Write(BitConverterLE.FromUInt32(40))
        self.Write(BitConverterLE.FromUInt32(0)) # width
        self.Write(BitConverterLE.FromUInt32(0)) # height
        self.Write(BitConverterLE.FromUInt16(1))
        self.Write(BitConverterLE.FromUInt16(24))
    
        self.WriteFourCC(self.CodecFourCC())
        self.Write(BitConverterLE.FromUInt32(0)) # biSizeImage
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
        self.Write(BitConverterLE.FromUInt32(0))
    
        self.WriteFourCC('LIST')
        self.Write(BitConverterLE.FromUInt32(0)) # chunk size
        self.WriteFourCC('movi')

    def WriteChunk(self, chunk, timeStamp, frameType):
        offset = 0
        length = len(chunk)

        if self._codecID == VideoTagHeader.VP6:
            offset = 1
            length -= 1
        elif self._codecID == VideoTagHeader.VP6v2:
            offset = 4
            if length >= 4:
                alphaOffset = BitConverterBE.ToUInt32(chunk, 0) & 0xffffff
                if not self._isAlphaWriter:
                    length = alphaOffset
                else:
                    offset += alphaOffset
                    length -= offset
            else:
                length = 0

        length = max(length, 0)
        length = min(length, len(chunk) - offset)

        self._index.append(0x10 if (frameType == 1) else 0)
        self._index.append(self._moviDataSize + 4)
        self._index.append(length)

        if (self._width == 0) and (self._height == 0):
            self.GetFrameSize(chunk)

        self.WriteFourCC('00dc')
        self.Write(BitConverterLE.FromInt32(length))
        self.Write(chunk, offset, length)

        if (length % 2) != 0:
            self.Write('\x00')
            length += 1

        self._moviDataSize += length + 8
        self._frameCount += 1

        if self._alphaWriter is not None:
            self._alphaWriter.WriteChunk(chunk, timeStamp, frameType)

    def GetFrameSize(self, chunk):
        if self._codecID == VideoTagHeader.H263:
            # Reference: flv_h263_decode_picture_header from libavcodec's h263.c
            if len(chunk) < 10: return

            x = c_ulonglong(BitConverterBE.ToUInt64(chunk, 2))

            if BitHelper.Read(x, 1) != 1:
                return

            BitHelper.Read(x, 5)
            BitHelper.Read(x, 8)

            _format = BitHelper.Read(x, 3)

            if _format == 0:
                self._width = BitHelper.Read(x, 8)
                self._height = BitHelper.Read(x, 8)
            elif _format == 1:
                self._width = BitHelper.Read(x, 16)
                self._height = BitHelper.Read(x, 16)
            elif _format == 2:
                self._width, self._height = VideoFormat.CIF
            elif _format == 3:
                self._width, self._height = VideoFormat.QCIF
            elif _format == 4:
                self._width, self._height = VideoFormat.SQCIF
            elif _format == 5:
                self._width, self._height = VideoFormat.QVGA
            elif _format == 6:
                self._width, self._height = VideoFormat.QQVGA

            #hdr = H263FrameHeader.from_buffer_copy(chunk)

            #if hdr.header != 1: # h263 header
            #    return

            #if hdr.picformat not in (0, 1): # picture format 0: h263 escape codes 1: 11-bit escape codes 
            #    return

        elif self._codecID in (VideoTagHeader.SCREEN, VideoTagHeader.SCREENv2): # FIXME: v2?
            # Reference: flashsv_decode_frame from libavcodec's flashsv.c
            # notice: libavcodec checks if width/height changes
            if len(chunk) < 4: return

            hdr = FLASHSVFrameHeader.from_buffer_copy(chunk)
            self._width = hdr.imageWidth
            self._height = hdr.imageHeight

        elif self._codecID in (VideoTagHeader.VP6, VideoTagHeader.VP6v2):
            # Reference: vp6_parse_header from libavcodec's vp6.c
            skip = 1 if (self._codecID == VideoTagHeader.VP6) else 4
            if len(chunk) < (skip + 8): return

            hdr = VP6FrameHeader.from_buffer_copy(chunk, skip)

            if hdr.deltaFrameFlag != 0:
                return

            if hdr.separatedCoeffFlag or hdr.filterHeader: # skip 16 bit
                xy = chunk[skip + 2:skip + 4]
            else:
                xy = chunk[skip:skip + 2]

            self._height = xy[0] * 16
            self._width = xy[1] * 16

            # chunk[0] contains the width and height (4 bits each, respectively) that should
            # be cropped off during playback, which will be non-zero if the encoder padded
            # the frames to a macroblock boundary.  But if you use this adjusted size in the
            # AVI header, DirectShow seems to ignore it, and it can cause stride or chroma
            # alignment problems with VFW if the width/height aren't multiples of 4.
            if not self._isAlphaWriter:
                cropX = chunk[0] >> 4
                cropY = chunk[0] & 0xf
                if (cropX != 0) or (cropY != 0):
                    self._warnings.append('Suggested cropping: %d pixels from right, %d pixels from bottom' % (cropX, cropY))

    __slots__ += [ '_indexChunkSize' ]
    def WriteIndexChunk(self):
        indexDataSize = self._frameCount * 16

        self.WriteFourCC('idx1')
        self.Write(BitConverterLE.FromUInt32(indexDataSize))

        for i in xrange(self._frameCount):
            self.WriteFourCC('00dc')
            self.Write(BitConverterLE.FromUInt32(self._index[(i * 3) + 0]))
            self.Write(BitConverterLE.FromUInt32(self._index[(i * 3) + 1]))
            self.Write(BitConverterLE.FromUInt32(self._index[(i * 3) + 2]))

        self._indexChunkSize = indexDataSize + 8

    def Finish(self, averageFrameRate):
        self.WriteIndexChunk()

        self.Seek(4)
        self.Write(BitConverterLE.FromUInt32(224 + self._moviDataSize + self._indexChunkSize - 8))

        self.Seek(24 + 8)
        self.Write(BitConverterLE.FromUInt32(0))
        self.Seek(12, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt32(self._frameCount))
        self.Seek(12, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt32(self._width))
        self.Write(BitConverterLE.FromUInt32(self._height))

        self.Seek(100 + 28)
        self.Write(BitConverterLE.FromUInt32(averageFrameRate.denominator))
        self.Write(BitConverterLE.FromUInt32(averageFrameRate.numerator))
        self.Seek(4, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt32(self._frameCount))
        self.Seek(16, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt16(self._width))
        self.Write(BitConverterLE.FromUInt16(self._height))

        self.Seek(164 + 12)
        self.Write(BitConverterLE.FromUInt32(self._width))
        self.Write(BitConverterLE.FromUInt32(self._height))
        self.Seek(8, SEEK_CUR)
        self.Write(BitConverterLE.FromUInt32(self._width * self._height * 6))

        self.Seek(212 + 4)
        self.Write(BitConverterLE.FromUInt32(self._moviDataSize + 4))

        self.Close()

        if self._alphaWriter is not None:
            self._alphaWriter.Finish(averageFrameRate)
            self._alphaWriter = None


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


##########################
### audio/mp3writer.py ###
##########################

from ctypes import BigEndianStructure, c_uint

# http://www.mp3-tech.org/programmer/frame_header.html

MPEG1BitRate        = [ 0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320 ]
MPEG2XBitRate       = [ 0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160 ]
MPEG1SampleRate     = [ 44100, 48000, 32000 ]
MPEG20SampleRate    = [ 22050, 24000, 16000 ]
MPEG25SampleRate    = [ 11025, 12000, 8000 ]

class MPEGVersion:
    MPEG25      = 0b00
    RESERVED    = 0b01
    MPEG2       = 0b10
    MPEG1       = 0b11

class LAYER:
    RESERVED    = 0b00
    LAYER3      = 0b01
    LAYER2      = 0b10
    LAYER1      = 0b11

class BITRATE:
    FREE        = 0b0000
    BAD         = 0b1111

class SAMPLERATE:
    RESERVED    = 0b11

class CHANNELMODE:
    STEREO      = 0b00
    JOINTSTEREO = 0b01
    DUALMONO    = 0b10
    MONO        = 0b11

class MP3FrameHeader(BigEndianStructure):
    _fields_ = [
                  ('frameSync',     c_uint, 11),
                  ('mpegVersion',   c_uint, 2),
                  ('layer',         c_uint, 2),
                  ('protectionBit', c_uint, 1),
                  ('bitRate',       c_uint, 4),
                  ('sampleRate',    c_uint, 2),
                  ('paddingBit',    c_uint, 1),
                  ('privateBit',    c_uint, 1),
                  ('channelMode',   c_uint, 2),
                  ('modeExt',       c_uint, 2),
                  ('copyright',     c_uint, 1),
                  ('original',      c_uint, 1),
                  ('emphasis',      c_uint, 2)
                  ]

class MP3Writer(AudioWriter):
    __slots__  = [ '_warnings', '_chunkBuffer', '_delayWrite', '_writeVBRHeader', '_totalFrameLength' ]
    __slots__ += [ '_frameOffsets', '_isVBR', '_hasVBRHeader', '_firstBitRate' ]
    __slots__ += [ '_mpegVersion', '_sampleRate', '_channelMode', '_firstFrameHeader' ]

    def __init__(self, path, warnings):
        super(MP3Writer, self).__init__(path)
        self._warnings = warnings
        self._delayWrite = True

        self._chunkBuffer = []
        self._frameOffsets = []

        self._isVBR = self._hasVBRHeader = self._writeVBRHeader = False
        self._firstBitRate = 0
        self._totalFrameLength = 0
        self._mpegVersion = self._sampleRate = self._channelMode = self._firstFrameHeader = 0

    def WriteChunk(self, chunk, timeStamp=None):
        self._chunkBuffer.append(chunk)
        self.ParseMP3Frames(chunk)

        if self._delayWrite and (self._totalFrameLength >= 65536):
            self._delayWrite = False
        if not self._delayWrite:
            self.Flush()

    def Finish(self):
        self.Flush()

        if self._writeVBRHeader:
            self.Seek(0)
            self.WriteVBRHeader(False)
        self.Close()

    def Flush(self):
        for chunk in self._chunkBuffer:
            self.Write(chunk)
        self._chunkBuffer = []

    def ParseMP3Frames(self, buff):
        offset = 0
        length = len(buff)

        while length >= 4:
            hdr = MP3FrameHeader.from_buffer_copy(buff, offset)

            if hdr.frameSync != 0b11111111111:
                print 'Invalid framesync', bin(hdr.frameSync)
                break

            if hdr.mpegVersion == MPEGVersion.RESERVED \
                or hdr.layer != LAYER.LAYER3 \
                or hdr.bitRate in (BITRATE.FREE, BITRATE.BAD) \
                or hdr.sampleRate == SAMPLERATE.RESERVED:
                print 'Invalid frame values'
                break

            bitRate = (MPEG1BitRate[hdr.bitRate] if (hdr.mpegVersion == MPEGVersion.MPEG1) else MPEG2XBitRate[hdr.bitRate]) * 1000
            if hdr.mpegVersion == MPEGVersion.MPEG1:
                sampleRate = MPEG1SampleRate[hdr.sampleRate]
            elif hdr.mpegVersion == MPEGVersion.MPEG2:
                sampleRate = MPEG20SampleRate[hdr.sampleRate]
            else:
                sampleRate = MPEG25SampleRate[hdr.sampleRate]

            frameLen = self.GetFrameLength(hdr.mpegVersion, bitRate, sampleRate, hdr.paddingBit)
            if frameLen > length:
                break

            isVBRHeaderFrame = False
            if len(self._frameOffsets) == 0:
                o = offset + self.GetFrameDataOffset(hdr.mpegVersion, hdr.channelMode)
                if buff[o:o + 4] == 'Xing':
                    isVBRHeaderFrame = True
                    self._delayWrite = False
                    self._hasVBRHeader = True

            if isVBRHeaderFrame:
                pass
            elif self._firstBitRate == 0:
                self._firstBitRate = bitRate
                self._mpegVersion = hdr.mpegVersion
                self._sampleRate = sampleRate
                self._channelMode = hdr.channelMode
                self._firstFrameHeader = BitConverterBE.ToUInt32(buff, offset)
            elif not self._isVBR and (bitRate != self._firstBitRate):
                self._isVBR = True
                if self._hasVBRHeader:
                    pass
                elif self._delayWrite:
                    self.WriteVBRHeader(True)
                    self._writeVBRHeader = True
                    self._delayWrite = False
                else:
                    self._warnings.append('Detected VBR too late, cannot add VBR header')

            self._frameOffsets.append(self._totalFrameLength + offset)

            offset += frameLen
            length -= frameLen
        self._totalFrameLength += len(buff)

    def WriteVBRHeader(self, isPlaceholder):
        buff = bytearray(self.GetFrameLength(self._mpegVersion, 64000, self._sampleRate, 0))
        if not isPlaceholder:
            header = self._firstFrameHeader
            dataOffset = self.GetFrameDataOffset(self._mpegVersion, self._channelMode)
            header &= 0xffff0dff    # Clear bitrate and padding fields
            header |= 0x00010000    # Set protection bit (indicates that CRC is NOT present)
            header |= (5 if self._mpegVersion == MPEGVersion.MPEG1 else 8) << 12 # 64 kbit/sec

            pos = 0                 ; buff[pos:pos + 4] = BitConverterBE.FromUInt32(header)

            pos = dataOffset        ; buff[pos:pos + 4] = 'Xing'
            pos = dataOffset + 4    ; buff[pos:pos + 4] = BitConverterBE.FromUInt32(0x7) # Flags
            pos = dataOffset + 8    ; buff[pos:pos + 4] = BitConverterBE.FromUInt32(len(self._frameOffsets))    # Frame count
            pos = dataOffset + 12   ; buff[pos:pos + 4] = BitConverterBE.FromUInt32(self._totalFrameLength)     # File Length 

            for i in xrange(100):
                frameIndex = int((i / 100.0) * len(self._frameOffsets))
                buff[dataOffset + 16 + i] = (self._frameOffsets[frameIndex] / float(self._totalFrameLength) * 250)
        self.Write(buff)

    @staticmethod
    def GetFrameLength(mpegVersion, bitRate, sampleRate, padding):
        return ((144 if (mpegVersion == MPEGVersion.MPEG1) else 72) * bitRate / sampleRate) + padding

    @staticmethod
    def GetFrameDataOffset(mpegVersion, channelMode):
        if mpegVersion == MPEGVersion.MPEG1:
            o = 17 if (channelMode == CHANNELMODE.MONO) else 32
        else:
            o = 9 if (channelMode == CHANNELMODE.MONO) else 17
        return o + 4


############################
### audio/speexwriter.py ###
############################

from ctypes import c_int

class OggPacket(object):
    __slots__ = [ 'GranulePosition', 'Data' ]

    def __init__(self, gp=0, data=None):
        self.GranulePosition = gp
        self.Data = data

class SpeexWriter(AudioWriter):
    __slots__  = [ '_serialNumber' ]

    _vendorString = 'FLV Extract'
    _sampleRate = 16000
    _msPerFrame = 20
    _samplesPerFrame = _sampleRate / (1000 / _msPerFrame)
    _targetPageDataSize = 4096

    __slots__ += [ '_packetList', '_packetListDataSize' ]
    __slots__ += ['_pageBuff', '_pageBuffOffset', '_pageSequenceNumber', '_granulePosition' ]
    def __init__(self, path, serialNumber):
        super(SpeexWriter, self).__init__(path)
        self._serialNumber = serialNumber

        self.Seek((28 + 80) + (28 + 8 + len(SpeexWriter._vendorString))) # Speex header + Vorbis comment
        self._packetList = []
        self._packetListDataSize = 0

        # Header + max segment table + target data size + extra segment
        self._pageBuff = bytearray(27 + 255 + SpeexWriter._targetPageDataSize + 254)

        self._pageBuffOffset = 0
        self._pageSequenceNumber = 2    # First audio packet
        self._granulePosition = 0

    _subModeSizes = [ 0, 43, 119, 160, 220, 300, 364, 492, 79 ]
    _wideBandSizes = [ 0, 36, 112, 192, 352 ]
    _inBandSignalSizes = [ 1, 1, 4, 4, 4, 4, 4, 4, 8, 8, 16, 16, 32, 32, 64, 64 ]

    def WriteChunk(self, chunk, timeStamp=None):
        frameStart = -1
        frameEnd = 0
        offset = c_int()
        length = len(chunk) * 8

        while (length - offset.value) >= 5:
            x = BitHelper.ReadB(chunk, offset, 1)
            if x != 0:
                # wideband frame
                x = BitHelper.ReadB(chunk, offset, 3)
                if not 1 <= x <= 4: raise Exception
                offset.value += SpeexWriter._wideBandSizes[x] - 4
            else:
                x = BitHelper.ReadB(chunk, offset, 4)
                if 1 <= x <= 8:
                    # narrowband frame
                    if frameStart != -1:
                        self.WriteFramePacket(chunk, frameStart, frameEnd)
                    frameStart = frameEnd
                    offset.value += SpeexWriter._subModeSizes[x] - 5
                elif x == 15:
                    # terminator
                    break
                elif x == 14:
                    # in-band signal
                    if (length - offset.value) < 4: raise Exception
                    x = BitHelper.ReadB(chunk, offset, 4)
                    offset.value += SpeexWriter._inBandSignalSizes[x]
                elif x == 13:
                    # custom in-band signal
                    if (length - offset.value) < 5: raise Exception
                    x = BitHelper.ReadB(chunk, offset, 5)
                    offset.value += x * 8
                else:
                    raise Exception

            frameEnd = offset.value

        if offset.value > length: raise Exception

        if frameStart != -1:
            self.WriteFramePacket(chunk, frameStart, frameEnd)

    def Finish(self):
        self.WritePage()
        self.FlushPage(True)
        self.Seek(0)
        self._pageSequenceNumber = 0
        self._granulePosition = 0
        self.WriteSpeexHeaderPacket()
        self.WriteVorbisCommentPacket()
        self.FlushPage(False)
        self.Close()

    def WriteFramePacket(self, data, startBit, endBit):
        lengthBits = endBit - startBit
        frame = BitHelper.CopyBlock(data, startBit, lengthBits)

        if (lengthBits % 8) != 0:
            frame[-1] |= 0xff >> ((lengthBits % 8) + 1) # padding

        self.AddPacket(frame, SpeexWriter._samplesPerFrame, True)

    def WriteSpeexHeaderPacket(self):
        data = bytearray(80)

        pos = 0         ; data[pos:pos + 8] = 'Speex   '    # speex_string
        pos = 8         ; data[pos:pos + 7] = 'unknown'     # speex_version
    
        data[28] = 1    # speex_version_id
        data[32] = 80   # header_size

        pos = 36        ; data[pos:pos + 4] = BitConverterLE.FromUInt32(SpeexWriter._sampleRate)       # rate

        data[40] = 1    # mode (e.g. narrowband, wideband)
        data[44] = 4    # mode_bitstream_version
        data[48] = 1    # nb_channels

        pos = 52        ; data[pos:pos + 4] = BitConverterLE.FromUInt32(0xffffffff)                     # -1: bitrate
        pos = 56        ; data[pos:pos + 4] = BitConverterLE.FromUInt32(SpeexWriter._samplesPerFrame)   # frame_size

        data[60] = 0    # vbr
        data[64] = 1    # frames_per_packet

        self.AddPacket(data, 0, False)

    def WriteVorbisCommentPacket(self):
        length = len(SpeexWriter._vendorString)
        data = bytearray(8 + length)
        data[0] = length

        pos = 4         ; data[pos:pos + length] = SpeexWriter._vendorString

        self.AddPacket(data, 0, False)

    def AddPacket(self, data, sampleLength, delayWrite):
        length = len(data)
        if length >= 255:
            raise Exception('Packet exceeds maximum size')

        self._granulePosition += sampleLength

        self._packetList.append(OggPacket(self._granulePosition, data))
        self._packetListDataSize += length

        if not delayWrite or (self._packetListDataSize >= self._targetPageDataSize) or (len(self._packetList) == 255):
            self.WritePage()

    def WritePage(self):
        numPackets = len(self._packetList)
        if numPackets == 0: return
        self.FlushPage(False)
        self.WriteToPage('OggS', 0, 4)

        self.WriteToPageUInt8(0)                                                    # Stream structure version
        self.WriteToPageUInt8(0x02 if (self._pageSequenceNumber == 0) else 0)       # Page flags
        self.WriteToPageUInt64(self._packetList[-1].GranulePosition)                # Position in samples
        self.WriteToPageUInt32(self._serialNumber)                                  # Stream serial number
        self.WriteToPageUInt32(self._pageSequenceNumber)                            # Page sequence number
        self.WriteToPageUInt32(0)                                                   # Checksum
        self.WriteToPageUInt8(numPackets)                                           # Page segment count

        for packet in self._packetList:
            self.WriteToPageUInt8(len(packet.Data))

        for packet in self._packetList:
            self.WriteToPage(packet.Data, 0, len(packet.Data))

        self._packetList = []
        self._packetListDataSize = 0
        self._pageSequenceNumber += 1

    def FlushPage(self, isLastPage):
        if self._pageBuffOffset == 0: return

        if isLastPage:
            self._pageBuff[5] |= 0x04

        crc = OggCRC.Calculate(self._pageBuff, 0, self._pageBuffOffset)
        pos = 22        ; self._pageBuff[pos:pos + 4] = BitConverterLE.FromUInt32(crc)
        self.Write(self._pageBuff, 0, self._pageBuffOffset)
        self._pageBuffOffset = 0

    def WriteToPage(self, data, offset, length):
        self._pageBuff[self._pageBuffOffset:self._pageBuffOffset + length] = data[offset:offset + length]
        self._pageBuffOffset += length

    def WriteToPageUInt8(self, value):
        self.WriteToPage(chr(value), 0, 1)

    def WriteToPageUInt32(self, value):
        self.WriteToPage(BitConverterLE.FromUInt32(value), 0, 4)

    def WriteToPageUInt64(self, value):
        self.WriteToPage(BitConverterLE.FromUInt64(value), 0, 8)


##########################
### audio/wavwriter.py ###
##########################

class WAVWriter(AudioWriter):
    __slots__  = [ 'blockAlign', '_bitsPerSample', '_channelCount', '_sampleRate', '_blockAlign' ]
    __slots__ += [ '_sampleLen', '_finalSampleLen', '_wroteHeaders' ]

    def __init__(self, path, bitsPerSample, channelCount, sampleRate):
        super(WAVWriter, self).__init__(path)

        self.blockAlign = (bitsPerSample / 8) * channelCount

        # WAVTools.WAVWriter
        self._bitsPerSample = bitsPerSample
        self._channelCount = channelCount
        self._sampleRate = sampleRate
        self._blockAlign = self._channelCount * ((self._bitsPerSample + 7) / 8)

        self._sampleLen = self._finalSampleLen = 0
        self._wroteHeaders = False

    def WriteChunk(self, chunk, timeStamp=None):
        self.WriteSamples(chunk, len(chunk) / self.blockAlign)

    def WriteHeaders(self):
        dataChunkSize = self.GetDataChunkSize(self._finalSampleLen)

        self.WriteFourCC('RIFF')
        self.Write(BitConverterLE.FromUInt32(dataChunkSize + (dataChunkSize & 1) + 36))
        self.WriteFourCC('WAVE')
        self.WriteFourCC('fmt ')
        self.Write(BitConverterLE.FromUInt32(16))
        self.Write(BitConverterLE.FromUInt16(1))
        self.Write(BitConverterLE.FromUInt16(self._channelCount))
        self.Write(BitConverterLE.FromUInt32(self._sampleRate))
        self.Write(BitConverterLE.FromUInt32(self._sampleRate * self._blockAlign))
        self.Write(BitConverterLE.FromUInt16(self._blockAlign))
        self.Write(BitConverterLE.FromUInt16(self._bitsPerSample))
        self.WriteFourCC('data')
        self.Write(BitConverterLE.FromUInt32(dataChunkSize))

    def GetDataChunkSize(self, sampleCount):
        maxFileSize = 0x7ffffffe

        dataSize = sampleCount * self._blockAlign
        if (dataSize + 44) > maxFileSize:
            dataSize = ((maxFileSize - 44) / self._blockAlign) * self._blockAlign
        return dataSize

    def Finish(self):
        if ((self._sampleLen * self._blockAlign) & 1) == 1:
            self.Write('\x00')

        if self._sampleLen != self._finalSampleLen:
            dataChunkSize = self.GetDataChunkSize(self._sampleLen)
            self.Seek(4)
            self.Write(BitConverterLE.FromUInt32(dataChunkSize + (dataChunkSize & 1) + 36))
            self.Seek(40)
            self.Write(BitConverterLE.FromUInt32(dataChunkSize))

        self.Close()

    def WriteSamples(self, buff, sampleCount):
        if sampleCount <= 0: return

        if not self._wroteHeaders:
            self.WriteHeaders()
            self._wroteHeaders = True

        self.Write(buff, 0, sampleCount * self._blockAlign)
        self._sampleLen += sampleCount
