##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Michael Stapelberg
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 3
    id = 'scs'
    name = 'SCS'
    longname = 'Sistema Cablaggio Semplificato (Simplified Cable Solution)'
    desc = 'fieldbus network protocol for home automation, used by bTicino and Legrand'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['IC', 'IR']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('startbit', 'start bit'),
        ('data', 'data bit'),
        ('stopbit', 'stop bit'),
        ('val', 'value'),
        ('telegram', 'telegram'),
        ('scs', 'scs'),
    )
    annotation_rows = (
        ('encoding', 'Encoding', (0, 2)),
        ('data', 'Data', (1,)),
        ('val', 'Value', (3,)),
        ('telegram', 'Telegram', (4,)),
        ('scs', 'SCS', (5,)),
    )
    options = ()

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplenumber_last = None
        self.pulses = []
        self.bits = []
        self.labels = []
        self.bit_count = 0
        self.ss = None
        self.es = None
        self.state = 'IDLE'
        self.telegram = []
        self.telegram_idx = []

    # called before beginning of decoding
    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    # called to start decoding
    def decode(self):
        while True:
            if len(self.telegram) == 7:
                self.put(self.telegram_idx[0][0], self.telegram_idx[6][1], self.out_ann, [4, ['7-byte SCS telegram']])
                self.annotate_telegram(0, [5, ['init']])
                self.annotate_telegram(1, [5, ['addr']])
                self.annotate_telegram(2, [5, ['??']])
                self.annotate_telegram(3, [5, ['request']])
                self.annotate_telegram(4, [5, ['??']])
                wantcrc = self.telegram[1] ^ self.telegram[2] ^ self.telegram[3] ^ self.telegram[4]
                crc = 'good' if wantcrc == self.telegram[5] else 'bad'
                self.annotate_telegram(5, [5, ['%s crc' % crc]])
                self.annotate_telegram(6, [5, ['term']])
                self.telegram = []
                self.telegram_idx = []
            # Wait for the start of a transmission:
            # the SCS start bit is always 0, i.e. 34us low, 70us high
            pin = self.wait({0: 'l'})
            start = self.samplenum
            self.discard_rest()
            end = self.samplenum

            self.put(start, end, self.out_ann, [0, ['start = %s' % pin]])

            startbitsample = self.samplenum
            val = 0
            for i in range(0, 8):
                bit = self.demodulate_databit()
                val = val | (int(bit[0]) << i)
            self.telegram = self.telegram + [val]
            self.telegram_idx = self.telegram_idx + [[startbitsample, self.samplenum]]
            self.put(startbitsample, self.samplenum, self.out_ann, [3, ['0x%x' % val]])

            # stop bit should be 1!
            self.expect_stop()

    # helper functions (not part of the decoder API) below:

    def discard_rest(self):
        # skip the remaining 16 samples (17 samples = 34us)
        self.wait({'skip': 16})
        # skip the remaining 35 samples (35 samples = 70us)
        # (skipping one extra sample to avoid going out of sync)
        self.wait({'skip': 36})
        
    def demodulate_databit(self):
        pin = self.wait()
        start = self.samplenum
        self.discard_rest()
        end = self.samplenum
        self.put(start, end, self.out_ann, [1, ['%s' % pin]])
        return pin

    def expect_stop(self):
        pin = self.wait()
        start = self.samplenum
        self.discard_rest()
        end = self.samplenum
        self.put(start, end, self.out_ann, [2, ['stop = %s' % pin]])

    def annotate_telegram(self, idx, data):
        start = self.telegram_idx[idx][0]
        end = self.telegram_idx[idx][1]
        self.put(start, end, self.out_ann, data)
