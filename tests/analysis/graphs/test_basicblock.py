# Copyright (c) 2014, Fundacion Dr. Manuel Sadosky
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import absolute_import

import os
import unittest

from barf.analysis.graphs import CFGRecoverer, ControlFlowGraph, RecursiveDescent
from barf.analysis.graphs.basicblock import BasicBlock
from barf.arch import ARCH_X86_MODE_32
from barf.arch.x86 import X86ArchitectureInformation
from barf.arch.x86.disassembler import X86Disassembler
from barf.arch.x86.parser import X86Parser
from barf.arch.x86.translator import X86Translator
from barf.core.binary import BinaryFile


def get_full_path(filename):
    return os.path.dirname(os.path.abspath(__file__)) + filename


class BinDiffTests(unittest.TestCase):

    def setUp(self):
        self._parser = X86Parser(ARCH_X86_MODE_32)
        self._translator = X86Translator(ARCH_X86_MODE_32)

    def test_equality(self):
        addr = 0x0804842f

        asm = self._parser.parse("cmp DWORD PTR [esp+0x18], 0x41424344")
        asm.address = 0x08048425
        asm.size = 8

        asm1 = [asm]

        asm = self._parser.parse("jne 0x08048445")
        asm.address = 0x0804842d
        asm.size = 2

        asm1 += [asm]

        ir1  = [self._translator.translate(asm1[0])]
        ir1 += [self._translator.translate(asm1[1])]

        asm = self._parser.parse("cmp DWORD PTR [esp+0x18], 0x41424344")
        asm.address = 0x08048425
        asm.size = 8

        asm2 = [asm]

        asm = self._parser.parse("jne 0x0804844f")
        asm.address = 0x0804842d
        asm.size = 2

        asm2 += [asm]

        ir2  = [self._translator.translate(asm2[0])]
        ir2 += [self._translator.translate(asm2[1])]

        bb1 = BasicBlock()
        asm1[0].ir_instrs = ir1[0]
        asm1[1].ir_instrs = ir1[1]
        bb1.instrs.append(asm1[0])
        bb1.instrs.append(asm1[1])

        bb2 = BasicBlock()
        asm2[0].ir_instrs = ir2[0]
        asm2[1].ir_instrs = ir2[1]
        bb2.instrs.append(asm2[0])
        bb2.instrs.append(asm2[1])

        self.assertTrue(bb1 == bb1)
        self.assertTrue(bb2 == bb2)

        # It will not assert true. Read comment on BasicBlock.__eq__
        # self.assertTrue(bb1 != bb2)


class X86CfgRecoveryTests(unittest.TestCase):

    def setUp(self):
        self._arch_mode = ARCH_X86_MODE_32
        self._arch_info = X86ArchitectureInformation(self._arch_mode)
        self._disassembler = X86Disassembler(ARCH_X86_MODE_32)
        self._translator = X86Translator(ARCH_X86_MODE_32)

    def test_sample_1(self):
        binary = BinaryFile(get_full_path("/data/bin/x86_sample_1"))
        strategy = RecursiveDescent(self._disassembler, binary.text_section, self._translator, self._arch_info)
        recoverer = CFGRecoverer(strategy)

        bbs, call_targets = recoverer.build(0x0804840b, 0x08048438)

        self.assertEqual(len(bbs), 1)

        cfg = ControlFlowGraph(bbs, name="main")

        self.assertEqual(cfg.start_address, 0x0804840b)
        self.assertEqual(cfg.end_address, 0x08048438)
        self.assertEqual(len(cfg.basic_blocks), 1)

    def test_sample_2(self):
        binary = BinaryFile(get_full_path("/data/bin/x86_sample_2"))
        strategy = RecursiveDescent(self._disassembler, binary.text_section, self._translator, self._arch_info)
        recoverer = CFGRecoverer(strategy)

        # Recover "main" function.
        bbs, call_targets = recoverer.build(0x0804846d, 0x080484a3)

        self.assertEqual(len(bbs), 4)

        cfg = ControlFlowGraph(bbs, name="main")

        self.assertEqual(cfg.start_address, 0x0804846d)
        self.assertEqual(cfg.end_address, 0x080484a3)
        self.assertEqual(len(cfg.basic_blocks), 4)

        bb_entry = cfg.find_basic_block(0x0804846d)
        self.assertEqual(len(bb_entry.branches), 2)
        self.assertEqual(bb_entry.taken_branch, 0x08048491)
        self.assertEqual(bb_entry.not_taken_branch, 0x0804848a)

        bb_taken = cfg.find_basic_block(0x08048491)
        self.assertEqual(len(bb_taken.branches), 1)
        self.assertEqual(bb_taken.taken_branch, None)
        self.assertEqual(bb_taken.not_taken_branch, None)
        self.assertEqual(bb_taken.direct_branch, 0x08048496)

        bb_not_taken = cfg.find_basic_block(0x0804848a)
        self.assertEqual(len(bb_not_taken.branches), 1)
        self.assertEqual(bb_not_taken.taken_branch, None)
        self.assertEqual(bb_not_taken.not_taken_branch, None)
        self.assertEqual(bb_not_taken.direct_branch, 0x08048496)

        # Recover "func_1" function.
        bbs, call_targets = recoverer.build(0x0804843b, 0x8048453)

        self.assertEqual(len(bbs), 1)

        cfg = ControlFlowGraph(bbs, name="main")

        self.assertEqual(cfg.start_address, 0x0804843b)
        self.assertEqual(cfg.end_address, 0x8048453)
        self.assertEqual(len(cfg.basic_blocks), 1)

        # Recover "func_2" function.
        bbs, call_targets = recoverer.build(0x08048454, 0x0804846c)

        self.assertEqual(len(bbs), 1)

        cfg = ControlFlowGraph(bbs, name="main")

        self.assertEqual(cfg.start_address, 0x08048454)
        self.assertEqual(cfg.end_address, 0x0804846c)
        self.assertEqual(len(cfg.basic_blocks), 1)


def main():
    unittest.main()


if __name__ == '__main__':
    main()
