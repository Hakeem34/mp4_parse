import os
import sys
import re
import time
import datetime
import subprocess


g_target_paths  = []
g_option_stdout = 1



#####################################################
# mp4フォーマットに関する定義
#####################################################
SIZE_BOX_SIZE           = 4
BOX_SIZE_EXTEND         = 0x00000001
SIZE_BOX_SIZE_EX        = 8

SIZE_BOX_TYPE           = 4
BOX_TYPE_ROOT           = 'root'          #/* 仮想のルートBOX */
BOX_TYPE_MOOV           = 'moov'
BOX_TYPE_MOOV_HEADER    = 'mvhd'
BOX_TYPE_TRACK          = 'trak'
BOX_TYPE_TRACK_HEADER   = 'tkhd'
BOX_TYPE_EDTS           = 'edts'
BOX_TYPE_MEDIA          = 'mdia'
BOX_TYPE_MEDIA_HEADER   = 'mdhd'
BOX_TYPE_MEDIA_INFO     = 'minf'
BOX_TYPE_DATA_INFO      = 'dinf'
BOX_TYPE_STBL           = 'stbl'
BOX_TYPE_UDTA           = 'udta'
BOX_TYPE_META           = 'meta'
BOX_TYPE_MVEX           = 'mvex'
BOX_TYPE_VM_HEADER      = 'vmhd'


#/* ヘッダ共通定義 */
SIZE_HEADER_VERSION     = 1
SIZE_HEADER_FLAG        = 3
SIZE_HEADER_VER0_SIZE   = 4
SIZE_HEADER_VER1_SIZE   = 8
SIZE_HEADER_TIME_SCALE  = 4

#/* mvhd関連定義 */
SIZE_MVHD_RATE          = 4
SIZE_MVHD_VOLUME        = 2
SIZE_MVHD_MATRIX        = 36
SIZE_MVHD_NEXT_TRACK_ID = 4

#/* tkhd関連定義 */
SIZE_TKHD_TRACK_ID      = 4
SIZE_TKHD_LAYER         = 2
SIZE_TKHD_ATG           = 2
SIZE_TKHD_VOLUME        = 2
SIZE_TKHD_MATRIX        = 36
SIZE_TKHD_WIDTH         = 4
SIZE_TKHD_HEIGHT        = 4

#/* mdhd関連定義 */
SIZE_MDHD_LANGUAGE      = 2
SIZE_MDHD_RESERVE       = 2

#/* vmhd関連定義 */
SIZE_VMHD_GRAPH_MODE    = 2
SIZE_VMHD_OP_COLOR      = 2


#PARENT_BOX_LIST         = ['moov', 'trak', 'edts', 'mdia', 'minf', 'dinf', 'stbl', 'udta', 'meta', 'mvex']
PARENT_BOX_LIST         = [
                              BOX_TYPE_MOOV,
                              BOX_TYPE_TRACK,
                              BOX_TYPE_EDTS,
                              BOX_TYPE_MEDIA,
                              BOX_TYPE_MEDIA_INFO,
                              BOX_TYPE_DATA_INFO,
                              BOX_TYPE_STBL,
                              BOX_TYPE_META,
                              BOX_TYPE_MVEX
                          ]



#####################################################
# BOX定義クラス
#####################################################
class cMP4_box:
    def __init__(self, addr, header_size, size, type, depth):
        self.addr                   = addr
        self.header_size            = header_size
        self.size                   = size
        self.type                   = type
        self.is_leaf                = 0
        self.children               = []
        self.body                   = None
        self.depth                  = depth
        return

    def add_child(self, box_data):
        self.children.append(box_data)
        return


#####################################################
# ビデオメディアヘッダ定義クラス
#####################################################
class cMP4_vmhd:
    def __init__(self):
        self.version                = 0
        self.flag                   = 0
        self.graphics_mode          = 0
        self.op_color_red           = 0
        self.op_color_green         = 0
        self.op_color_blue          = 0
        return


#####################################################
# メディアヘッダ定義クラス
#####################################################
class cMP4_mdhd:
    def __init__(self):
        self.version                = 0
        self.flag                   = 0
        self.created_time           = 0
        self.modified_time          = 0
        self.time_scale             = 0
        self.duration               = 0
        self.language               = 0
        self.reserve                = 0
        return


#####################################################
# トラックヘッダ定義クラス
#####################################################
class cMP4_tkhd:
    def __init__(self):
        self.version                = 0
        self.flag                   = 0
        self.created_time           = 0
        self.modified_time          = 0
        self.track_id               = 0
        self.duration               = 0
        self.layer                  = 0
        self.alt_track_group        = 0
        self.volume                 = 0
        self.matrix_data            = None
        self.width                  = 0
        self.height                 = 0
        return


#####################################################
# moovヘッダ定義クラス
#####################################################
class cMP4_mvhd:
    def __init__(self):
        self.version                = 0
        self.flag                   = 0
        self.created_time           = 0
        self.modified_time          = 0
        self.time_scale             = 0
        self.duration               = 0
        self.rate                   = 0
        self.volume                 = 0
        self.matrix_data            = None
        self.next_track_id          = 0
        return


#####################################################
# box情報読み出し
#####################################################
def read_box_header(file, depth):
#   print("read_box_header depth:%d" % depth)
    addr = file.seek(0, os.SEEK_CUR)
    data = file.read(SIZE_BOX_SIZE)
    block_size = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_BOX_TYPE)
    block_type = chr(data[0]) + chr(data[1]) + chr(data[2]) + chr(data[3])

    if (block_size == BOX_SIZE_EXTEND):
        data = file.read(SIZE_BOX_SIZE_EX)
        block_size = int.from_bytes(data, byteorder='big')
        header_size = SIZE_BOX_SIZE + SIZE_BOX_TYPE + SIZE_BOX_SIZE_EX
    else:
        header_size = SIZE_BOX_SIZE + SIZE_BOX_TYPE


#   print("[%08x]+[%08x][%d]" % (addr, block_size, depth), end = "")
    print("[%08x]+[%08x]" % (addr, block_size), end = "")
    print("  " * (depth - 1), end = "")

#   print("block_size : 0x%08x block_type : %s" % (block_size, block_type))
    print("[%s]" % (block_type))

    box_data = cMP4_box(addr, header_size, block_size, block_type, depth)
    return box_data


#####################################################
# Media Header情報読み出し
#####################################################
def read_video_media_header_data(file, parent_box):
    vmhd = cMP4_vmhd()

    data = file.read(SIZE_HEADER_VERSION)
    vmhd.version = int.from_bytes(data, byteorder='big')
    if (vmhd.version == 0):
        read_size = SIZE_HEADER_VER0_SIZE
    else:
        read_size = SIZE_HEADER_VER1_SIZE

    data = file.read(SIZE_HEADER_FLAG)
    vmhd.flag = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_VMHD_GRAPH_MODE)
    vmhd.graphics_mode = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_VMHD_OP_COLOR)
    vmhd.op_color_red = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_VMHD_OP_COLOR)
    vmhd.op_color_green = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_VMHD_OP_COLOR)
    vmhd.op_color_blue = int.from_bytes(data, byteorder='big')

    print("    vmhd : version   : 0x%02x" % vmhd.version)
    print("    vmhd : flag      : 0x%06x" % vmhd.flag)
    print("    vmhd : graph mode: 0x%04x" % vmhd.graphics_mode)
    print("    vmhd : op col R  : 0x%04x" % vmhd.op_color_red)
    print("    vmhd : op col G  : 0x%04x" % vmhd.op_color_green)
    print("    vmhd : op col B  : 0x%04x" % vmhd.op_color_blue)
    parent_box.body = vmhd
    return


#####################################################
# Media Header情報読み出し
#####################################################
def read_media_header_data(file, parent_box):
    mdhd = cMP4_mdhd()
    end_of_box = parent_box.addr + parent_box.size

    data = file.read(SIZE_HEADER_VERSION)
    mdhd.version = int.from_bytes(data, byteorder='big')
    if (mdhd.version == 0):
        read_size = SIZE_HEADER_VER0_SIZE
    else:
        read_size = SIZE_HEADER_VER1_SIZE

    data = file.read(SIZE_HEADER_FLAG)
    mdhd.flag = int.from_bytes(data, byteorder='big')

    data = file.read(read_size)
    mdhd.created_time = int.from_bytes(data, byteorder='big')
    data = file.read(read_size)
    mdhd.modified_time = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_HEADER_TIME_SCALE)
    mdhd.time_scale = int.from_bytes(data, byteorder='big')

    data = file.read(read_size)
    mdhd.duration = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_MDHD_LANGUAGE)
    mdhd.language = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_MDHD_RESERVE)
    mdhd.reserve = int.from_bytes(data, byteorder='big')


    print("    mdhd : version   : 0x%02x" % mdhd.version)
    print("    mdhd : flag      : 0x%06x" % mdhd.flag)
    print("    mdhd : c time    : 0x%08x" % mdhd.created_time)
    print("    mdhd : m time    : 0x%08x" % mdhd.modified_time)
    print("    mdhd : duration  : 0x%08x" % mdhd.duration)
    print("    mdhd : language  : 0x%04x" % mdhd.language)
    print("    mdhd : reserve   : 0x%04x" % mdhd.reserve)
    parent_box.body = mdhd
    return


#####################################################
# Track Header情報読み出し
#####################################################
def read_track_header_data(file, parent_box):
    tkhd = cMP4_tkhd()
    end_of_box = parent_box.addr + parent_box.size

    data = file.read(SIZE_HEADER_VERSION)
    tkhd.version = int.from_bytes(data, byteorder='big')
    if (tkhd.version == 0):
        read_size = SIZE_HEADER_VER0_SIZE
    else:
        read_size = SIZE_HEADER_VER1_SIZE

    data = file.read(SIZE_HEADER_FLAG)
    tkhd.flag = int.from_bytes(data, byteorder='big')

    data = file.read(read_size)
    tkhd.created_time = int.from_bytes(data, byteorder='big')
    data = file.read(read_size)
    tkhd.modified_time = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_TKHD_TRACK_ID)
    tkhd.track_id = int.from_bytes(data, byteorder='big')

    #/* Reserve */
    data = file.read(4)

    data = file.read(read_size)
    tkhd.duration = int.from_bytes(data, byteorder='big')

    #/* Reserve */
    data = file.read(8)

    data = file.read(SIZE_TKHD_LAYER)
    tkhd.layer = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_TKHD_ATG)
    tkhd.alt_track_group = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_TKHD_VOLUME)
    tkhd.volume = int.from_bytes(data, byteorder='big')

    tkhd.matrix_data = file.read(SIZE_TKHD_MATRIX)

    data = file.read(SIZE_TKHD_WIDTH)
    tkhd.width = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_TKHD_HEIGHT)
    tkhd.height = int.from_bytes(data, byteorder='big')

    print("    tkhd : version   : 0x%02x" % tkhd.version)
    print("    tkhd : flag      : 0x%06x" % tkhd.flag)
    print("    tkhd : c time    : 0x%08x" % tkhd.created_time)
    print("    tkhd : m time    : 0x%08x" % tkhd.modified_time)
    print("    tkhd : track id  : 0x%08x" % tkhd.track_id)
    print("    tkhd : duration  : 0x%08x" % tkhd.duration)
    print("    tkhd : layer     : 0x%08x" % tkhd.layer)
    print("    tkhd : alt group : 0x%08x" % tkhd.alt_track_group)
    print("    tkhd : volume    : 0x%04x" % tkhd.volume)
    print("    tkhd : width     : %d"     % tkhd.width)
    print("    tkhd : height    : %d"     % tkhd.height)
    parent_box.body = tkhd
    return


#####################################################
# moov Header情報読み出し
#####################################################
def read_moov_header_data(file, parent_box):
    tkhd = cMP4_mvhd()
    end_of_box = parent_box.addr + parent_box.size

    data = file.read(SIZE_HEADER_VERSION)
    tkhd.version = int.from_bytes(data, byteorder='big')
    if (tkhd.version == 0):
        read_size = SIZE_HEADER_VER0_SIZE
    else:
        read_size = SIZE_HEADER_VER1_SIZE

    data = file.read(SIZE_HEADER_FLAG)
    tkhd.flag = int.from_bytes(data, byteorder='big')

    data = file.read(read_size)
    tkhd.created_time = int.from_bytes(data, byteorder='big')
    data = file.read(read_size)
    tkhd.modified_time = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_HEADER_TIME_SCALE)
    tkhd.time_scale = int.from_bytes(data, byteorder='big')

    data = file.read(read_size)
    tkhd.duration = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_MVHD_RATE)
    tkhd.rate = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_MVHD_VOLUME)
    tkhd.volume = int.from_bytes(data, byteorder='big')

    #/* Reserve */
    data = file.read(10)

    tkhd.matrix_data = file.read(SIZE_TKHD_MATRIX)

    #/* PreDefined */
    data = file.read(4*6)

    data = file.read(SIZE_MVHD_NEXT_TRACK_ID)
    tkhd.next_track_id = int.from_bytes(data, byteorder='big')

    print("    mvhd : version    : 0x%02x" % tkhd.version)
    print("    mvhd : flag       : 0x%06x" % tkhd.flag)
    print("    mvhd : c time     : 0x%08x" % tkhd.created_time)
    print("    mvhd : m time     : 0x%08x" % tkhd.modified_time)
    print("    mvhd : time_scale : 0x%08x" % tkhd.time_scale)
    print("    mvhd : rate       : 0x%08x" % tkhd.rate)
    print("    mvhd : duration   : 0x%08x" % tkhd.duration)
    print("    mvhd : volume     : 0x%04x" % tkhd.volume)
    print("    mvhd : next track : 0x%08x" % tkhd.next_track_id)
    parent_box.body = tkhd
    return


#####################################################
# 親となるboxの情報読み出し
#####################################################
def read_parent_box(file, parent_box):
    read_size = 0
    index = file.seek(0, os.SEEK_CUR)
#   print("read_parent_box start depth : %d, size:%d" % (parent_box.depth, parent_box.size))
    while (read_size < parent_box.size):
        box_data = read_box_header(file, parent_box.depth + 1)
        read_size += (box_data.header_size + box_data.size)

        if (box_data.type == BOX_TYPE_MOOV_HEADER):
            read_moov_header_data(file, box_data)
        elif (box_data.type == BOX_TYPE_TRACK_HEADER):
            read_track_header_data(file, box_data)
        elif (box_data.type == BOX_TYPE_MEDIA_HEADER):
            read_media_header_data(file, box_data)
        elif (box_data.type == BOX_TYPE_VM_HEADER):
            read_video_media_header_data(file, box_data)
        else:
            for parent_box_type in PARENT_BOX_LIST:
                if (box_data.type == parent_box_type):
                    read_parent_box(file, box_data)


        index = file.seek(index + box_data.size)
        parent_box.add_child(box_data)

#   print("read_parent_box end   depth : %d" % parent_box.depth)
    return read_size


#####################################################
# mp4ファイル解析
#####################################################
def parse_file_mp4(file_path):
    global g_sections
    global g_option_stdout

    if (g_option_stdout == 0):
        #/* 標準出力オプションでなければ、対象ファイル名に.txtを付与して出力 */
        log_path = file_path + '.txt'
        log_file = open(log_path, "w")
        sys.stdout = log_file

    start_time = parse_start()

    f = open(file_path, 'rb')
    eof = f.seek(0,os.SEEK_END)
    print("eof : 0x%08x" % eof)
    root_box = cMP4_box(0, 0, eof, BOX_TYPE_ROOT, 0)
    f.seek(0)
    read_parent_box(f, root_box)

    parse_end(start_time)
    f.close()
    return


#####################################################
# 処理開始時間計測
#####################################################
def parse_start():
    start_time = time.perf_counter()
    now = datetime.datetime.now()
    print("mp4解析開始 : " + str(now))
    return start_time


#####################################################
# 処理終了時間計測
#####################################################
def parse_end(start_time):
    end_time = time.perf_counter()
    now = datetime.datetime.now()
    print("mp4解析終了 : " + str(now))
    second = int(end_time - start_time)
    msec   = ((end_time - start_time) - second) * 1000
    minute = second / 60
    second = second % 60
    print("  %dmin %dsec %dmsec" % (minute, second, msec))
    return


#/*****************************************************************************/
#/* コマンドライン引数処理                                                    */
#/*****************************************************************************/
def check_command_line_option():
    global g_target_paths

    argc = len(sys.argv)
    option = ""

    if (argc == 1):
        print("usage : mp4_parse.py [target]")
        sys.exit(0)

    sys.argv.pop(0)
    for arg in sys.argv:
        if (os.path.isfile(arg)):
            g_target_paths.append(arg)
        else:
            print("invalid arg : %s" % arg)

    return


#/*****************************************************************************/
#/* メイン関数                                                                */
#/*****************************************************************************/
def main():
    check_command_line_option()

    for path in g_target_paths:
        parse_file_mp4(path)

    return

if __name__ == "__main__":
    main()





