#!/usr/bin/env python

import argparse, re, struct, sys

# == code derived from https://github.com/jangler/s3mml ==

class obj():
    def __init__(self):
        pass

def read_s3m(f):
    buf = bytes(f.read())
    m = obj()
    read_s3m_header(buf, m)
    read_s3m_instruments(buf, m)
    return m

def read_s3m_header(buf, m):
    m.title = struct.unpack_from('28s', buf, 0)[0].decode('ascii').strip('\0')
    m.numorders, m.numinstruments, m.numpatterns, m.flags, m.trackerversion, \
        m.sampletype = struct.unpack_from('6H', buf, 32)
    m.globalvolume, m.initialspeed, m.initialtempo, m.mastervolume, \
        m.ultraclickremoval, m.defaultpan = struct.unpack_from('6B', buf, 48)
    m.channelsettings = struct.unpack_from('32B', buf, 64)
    pos = 96
    m.orderlist = struct.unpack_from('%dB' % m.numorders, buf, pos)
    pos += m.numorders
    m.ptrinstruments = [x*16 for x in
            struct.unpack_from('%dH' % m.numinstruments, buf, pos)]
    pos += m.numinstruments * 2
    m.ptrpatterns = [x*16 for x in
            struct.unpack_from('%dH' % m.numpatterns, buf, pos)]

def read_s3m_instruments(buf, m):
    m.instruments = []
    for ptr in m.ptrinstruments:
        inst = obj()
        inst.type = struct.unpack_from('B', buf, ptr)[0]
        inst.filename = struct.unpack_from('12s', buf, ptr +
            1)[0].decode('ascii').strip('\0')

        oplvalues = struct.unpack_from('12B', buf, ptr + 16)
        inst.feedback = oplvalues[10] >> 1
        inst.connection = oplvalues[10] & 1 != 0
        inst.fbconnraw = oplvalues[10]
        inst.carrier, inst.modulator = obj(), obj()
        for offset, op in enumerate([inst.modulator, inst.carrier]):
            op.tremolo = oplvalues[offset] & 0x80 != 0
            op.vibrato = oplvalues[offset] & 0x40 != 0
            op.sustainsound = oplvalues[offset] & 0x20 != 0
            op.scaleenv = oplvalues[offset] & 0x10 != 0
            op.freqmult = oplvalues[offset] & 0xf
            op.levelscaling = (oplvalues[offset+2] & 0xc0) >> 6
            op.volume = 63 - (oplvalues[offset+2] & 0x3f)
            op.attack = (oplvalues[offset+4] & 0xf0) >> 4
            op.decay = oplvalues[offset+4] & 0x0f
            op.sustain = 15 - ((oplvalues[offset+6] & 0xf0) >> 4)
            op.release = oplvalues[offset+6] & 0x0f
            op.waveselect = oplvalues[offset+8]
            op.raw = bytes(oplvalues[offset:offset+9:2])

        inst.volume, inst.c2spd = struct.unpack_from('B3xI', buf, ptr + 28)
        inst.title = struct.unpack_from('28s', buf, ptr +
                36)[0].decode('ascii').strip('\0')
        m.instruments.append(inst)

# == end s3mml-derived code ==

def write_wopl(instruments, f):
    # determine instrument locations
    prog_map, perc_map = {}, {}
    for i, inst in enumerate(instruments):
        match = re.search(r'\[(\d+)\]', inst.title)
        if match:
            prog_map[int(match[1])-1] = inst
        match = re.search(r'<(\d+)>', inst.title)
        if match:
            perc_map[int(match[1])] = inst

    # header
    f.write(b'WOPL3-BANK\0') # magic "number"
    f.write(struct.pack('<H', 3)) # version
    f.write(struct.pack('>HHBB', 1, 1 if perc_map else 0, 0, 0)) # other header data

    # bank info
    f.write(struct.pack('32sBB', b'melodic', 0, 0))
    if perc_map:
        f.write(struct.pack('32sBB', b'percussion', 0, 0))

    # melodic instrument
    for i in range(128):
        if i in prog_map:
            write_opli(prog_map[i], f)
        elif i < len(instruments):
            write_opli(instruments[i], f)
        else:
            write_opli(None, f)
        f.write(struct.pack('4x'))

    # percussion instruments
    if perc_map:
        for i in range(128):
            write_opli(perc_map.get(i), f, 24)
            f.write(struct.pack('4x'))

def write_opli(inst, f, perc_key=0):
    if inst is None:
        f.write(struct.pack('32s7xB22x', b'undefined', 4))
        return
    f.write(struct.pack('>32shhbb4B',
        inst.title.encode('ascii'),
        0, # first voice key offset
        0, # second voice key offset
        0, # velocity offset
        0, # second voice detune
        perc_key, # percussion instrument key number
        0, # flags
        inst.fbconnraw, # feedback/connection for first voice
        0)) # feedback/connection for second voice
    for op in (inst.carrier, inst.modulator):
        f.write(op.raw)
    f.write(struct.pack('10x')) # ops 3 and 4

def fatal(e):
    print(e, file=sys.stderr)
    exit(1)

def convert(args):
    # read .s3m
    try:
        with open(args.src, 'rb') as f:
            s3m = read_s3m(f)
    except OSError as e:
        fatal(e)

    # write .wopl
    try:
        path = args.dst if args.dst else sys.argv[1].replace('.s3m', '.wopl')
        with open(path, 'wb') as f:
            write_wopl(s3m.instruments, f)
    except OSError as e:
        fatal(e)

def main():
    # handle CLI args
    parser = argparse.ArgumentParser(description='Convert a S3M to a WOPL instrument set.')
    parser.add_argument('src', type=str, help='source .s3m file')
    parser.add_argument('dst', type=str, nargs='?', help='destination .wopl file')
    parser.add_argument('-m', '--monitor', action='store_true',
            help='monitor filesystem for changes (requires watchdog)')
    args = parser.parse_args()

    # run once
    convert(args)

    # then monitor if necessary. monitoring the file itself can break if the
    # file is replaced, so we monitor the directory instead
    if args.monitor:
        import time
        from os.path import abspath, dirname
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError as e:
            fatal(e)
        path = dirname(abspath(args.src))
        handler = FileSystemEventHandler()
        def handle_fs_event(event):
            if event.event_type == 'modified' and abspath(event.src_path) == abspath(args.src):
                convert(args)
        handler.on_any_event = handle_fs_event
        observer = Observer()
        observer.schedule(handler, path)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

if __name__ == '__main__':
    main()
