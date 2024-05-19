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
BOX_TYPE_MOOV           = 'moov'
BOX_TYPE_MOOV_HEADER    = 'mvhd'
BOX_TYPE_TRACK          = 'trak'
BOX_TYPE_TRACK_HEADER   = 'tkhd'

SIZE_MVHD_VERSION       = 1
SIZE_MVHD_FLAG          = 3
SIZE_MVHD_VER0_SIZE     = 4
SIZE_MVHD_VER1_SIZE     = 8
SIZE_MVHD_TIME_SCALE    = 4
SIZE_MVHD_RATE          = 4
SIZE_MVHD_VOLUME        = 2
SIZE_MVHD_MATRIX        = 36
SIZE_MVHD_NEXT_TRACK_ID = 4

SIZE_TKHD_VERSION       = 1
SIZE_TKHD_FLAG          = 3
SIZE_TKHD_VER0_SIZE     = 4
SIZE_TKHD_VER1_SIZE     = 8
SIZE_TKHD_TRACK_ID      = 4
SIZE_TKHD_LAYER         = 2
SIZE_TKHD_ATG           = 2
SIZE_TKHD_VOLUME        = 2
SIZE_TKHD_MATRIX        = 36
SIZE_TKHD_WIDTH         = 4
SIZE_TKHD_HEIGHT        = 4




#####################################################
# BOX定義クラス
#####################################################
class cMP4_box:
    def __init__(self, addr, size, type):
        self.addr                   = addr
        self.size                   = size
        self.type                   = type
        self.is_leaf                = 0
        self.children               = []
        self.body                   = None
        return

    def add_child(self, box_data):
        self.children.append(box_data)
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
def read_box_header(file, indent):
    addr = file.seek(0, os.SEEK_CUR)
    data = file.read(SIZE_BOX_SIZE)
    block_size = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_BOX_TYPE)
    block_type = chr(data[0]) + chr(data[1]) + chr(data[2]) + chr(data[3])

    if (block_size == BOX_SIZE_EXTEND):
        data = file.read(SIZE_BOX_SIZE_EX)
        block_size = int.from_bytes(data, byteorder='big')


    print("[%08x]+[%08x]" % (addr, block_size), end = "")
    while(indent > 0):
        print(" ", end = "")
        indent -= 1

#   print("block_size : 0x%08x block_type : %s" % (block_size, block_type))
    print("[%s]" % (block_type))

    box_data = cMP4_box(addr, block_size, block_type)
    return box_data


#####################################################
# Track Header情報読み出し
#####################################################
def read_track_header_data(file, parent_box):
    tkhd = cMP4_tkhd()
    end_of_box = parent_box.addr + parent_box.size

    data = file.read(SIZE_TKHD_VERSION)
    tkhd.version = int.from_bytes(data, byteorder='big')
    if (tkhd.version == 0):
        read_size = SIZE_TKHD_VER0_SIZE
    else:
        read_size = SIZE_TKHD_VER1_SIZE

    data = file.read(SIZE_TKHD_FLAG)
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

    data = file.read(SIZE_MVHD_VERSION)
    tkhd.version = int.from_bytes(data, byteorder='big')
    if (tkhd.version == 0):
        read_size = SIZE_MVHD_VER0_SIZE
    else:
        read_size = SIZE_MVHD_VER1_SIZE

    data = file.read(SIZE_MVHD_FLAG)
    tkhd.flag = int.from_bytes(data, byteorder='big')

    data = file.read(read_size)
    tkhd.created_time = int.from_bytes(data, byteorder='big')
    data = file.read(read_size)
    tkhd.modified_time = int.from_bytes(data, byteorder='big')

    data = file.read(SIZE_MVHD_TIME_SCALE)
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
# trak boxの情報読み出し
#####################################################
def read_track_box(file, parent_box):
    index = file.seek(0, os.SEEK_CUR)
    read_size = 0
    end_of_box = parent_box.addr + parent_box.size

#   print ("  index:0x%08x, end_of_box:0x%08x" % (index, end_of_box))
    while (index < end_of_box):
        box_data = read_box_header(file, 4)
        read_size += box_data.size

        if (box_data.type == BOX_TYPE_TRACK_HEADER):
            read_track_header_data(file, box_data)

        index = file.seek(index + box_data.size)
#       print ("    index:0x%08x, read_size:%d" % (index, read_size))
        parent_box.add_child(box_data)

    return read_size


#####################################################
# moov boxの情報読み出し
#####################################################
def read_moov_box(file, parent_box):
    read_size = 0
    index = file.seek(0, os.SEEK_CUR)
    while (read_size < parent_box.size):
        box_data = read_box_header(file, 2)
        read_size += box_data.size

        if (box_data.type == BOX_TYPE_MOOV_HEADER):
            read_moov_header_data(file, box_data)
        elif (box_data.type == BOX_TYPE_TRACK):
            read_track_box(file, box_data)

        index = file.seek(index + box_data.size)
        parent_box.add_child(box_data)

    return read_size


#####################################################
# mp4ファイル解析
#####################################################
def parse_file_mp4(file_path):
    global g_sections
    global g_option_stdout

    index = 0

    if (g_option_stdout == 0):
        #/* 標準出力オプションでなければ、対象ファイル名に.txtを付与して出力 */
        log_path = file_path + '.txt'
        log_file = open(log_path, "w")
        sys.stdout = log_file

    start_time = parse_start()

    f = open(file_path, 'rb')
    eof = f.seek(0,os.SEEK_END)
    print("eof : 0x%08x" % eof)

    f.seek(0)
    box_data = read_box_header(f, 0)
    block_size = box_data.size
    index = f.seek(index + block_size)
#   print("index : 0x%08x" % index)

    while (index < eof):
        box_data = read_box_header(f, 0)
        block_size = box_data.size

        if (box_data.type == BOX_TYPE_MOOV):
            read_moov_box(f, box_data)

        index = f.seek(index + block_size)

#       print("index : 0x%08x" % index)

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





