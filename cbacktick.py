#!/usr/bin/env python3
import os, sys, subprocess

if not os.path.isdir('holypycparser'):
	cmd = 'git clone --depth 1 https://github.com/brentharts/holypycparser.git'
	print(cmd)
	subprocess.check_call(cmd.split())


sys.path.append('./holypycparser')
import holyguacamole as guaca
print(guaca)

def decomp(o):
	objdump_output = subprocess.check_output(["riscv64-linux-gnu-objdump", "-d", o]).decode("utf-8")
	asm = []
	sects = {}
	info = {'sections':sects, 'asm':asm}
	sect  = None
	current_section = None
	for ln in objdump_output.splitlines():
		if '--verbose' in sys.argv: print(ln)
		if ln.startswith("Disassembly of section"):
			current_section = ln.split()[-1]
			sect = {}
			sects[current_section]=sect
			continue

		elif ln.strip().endswith(':'):  ## label
			asm.append(ln[ln.index(' '):])
			print(asm[-1])
		elif ':' in ln:
			if ln.startswith('./') and 'file format' in ln: continue
			if '--verbose' in sys.argv: asm.append('#'+ln)
			a = ln[ ln.index(':')+1 : ].strip().split()[1:]
			print(a)
			a = ' '.join(a)
			asm.append(a)

		if current_section:
			if ln.startswith('  ') and ':' in ln:
				ops = None
				if '<' in ln:
					ln, comment = ln.split('<')
				if '#' in ln:
					ln, comment2 = ln.split('#')

				if ln.count(':')==1:
					mem, ln = ln.split(':')

				a = ln.split()
				if len(a)==3:
					mem2, inst, ops = a
				elif len(a)==2: ## some inst have no ops, like ret,mret,nop..
					mem2, inst = a
				else:
					raise RuntimeError(len(a))
				#print(a)
				if ops:
					for b in ops.split(','):
						if b in guaca.REGS:
							if b not in sect: sect[b] = {'count':0,'asm':[]}
							sect[b]['count'] += 1
							sect[b]['asm'].append(ln)
						## only checking the first operand
						break

	return info


def print_regs(register_usage):
	for section, registers in register_usage.items():
		print(section)
		for reg in registers:
			if reg in guaca.reg_colors:
				print('\033[%sm' % guaca.reg_colors[reg], end='')
			elif reg.startswith('a'):
				if reg in guaca.A_COLORS:
					clr = '48;5;%s' % guaca.A_COLORS[reg]
				else:
					clr = '30;44'
				print('\033[%sm' % clr, end='')
			elif reg.startswith('s'):
				if reg in guaca.S_COLORS:
					clr = '48;5;%s' % guaca.S_COLORS[reg]
				else:
					clr = '30;43'
				print('\033[%sm' % clr, end='')
			print('	%s : %s' %(reg, registers[reg]['count']), end='')
			print('\033[0m')
			if registers[reg]['count'] <= 10:
				for asm in registers[reg]['asm']:
					print('		: %s' %(asm))

def asm2json(asm):
	bareasm = None
	out = {'labels':{}, 'data':[]}
	lab = None
	for idx, ln in enumerate(asm):
		a = guaca.parse_asm(ln, term_colors=False)
		if 'label' in a:
			lab = a['label']
			out['labels'][lab] = []
		elif 'data' in a:
			out['data'].append(a)
		else:
			if lab:
				out['labels'][lab].append(a)
			else:
				if bareasm is None:
					bareasm = lab = '__bareasm__'
					out['labels'][lab] = []
				out['labels'][lab].append(a)
	return out

def mklinux():
	## https://risc-v-getting-started-guide.readthedocs.io/en/latest/linux-qemu.html
	if not os.path.isfile('/usr/bin/riscv64-linux-gnu-gcc'):
		os.system('sudo apt-get install gcc-riscv64-linux-gnu')

	if not os.path.isdir('linux'):
		cmd = 'git clone --depth 1 https://github.com/torvalds/linux.git'.split()
		print(cmd)
		subprocess.check_call(cmd)

	vmlinux = './linux/vmlinux'
	if not os.path.isfile(vmlinux) or '--rebuild' in sys.argv:
		cmd = 'make V=1 ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- defconfig'.split()
		print(cmd)
		subprocess.check_call(cmd, cwd='./linux')
		cmd = 'make V=1 ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu-'.split()
		print(cmd)
		subprocess.check_call(cmd, cwd='./linux')

	subprocess.check_call(['ls', '-lh', './linux/vmlinux'])

	info = decomp( './linux/virt/kvm/kvm_main.o' )
	print_regs(info['sections'])
	guaca.print_asm( '\n'.join(info['asm']) )
	d = asm2json(info['asm'])
	#print(d)

if __name__ == '__main__':
	out = None
	c = None
	includes = []
	defines  = []
	if '-o' in sys.argv:
		out = sys.argv[sys.argv.index('-o')+1]
	for arg in sys.argv:
		if arg.startswith('-I~/'): includes.append(os.path.expanduser(arg[2:]))
		elif arg.startswith('-I'): includes.append(arg)
		elif arg.startswith('-D'): defines.append(arg)

	for arg in sys.argv:
		if arg.endswith('.c'):
			c = arg
			if out: assert os.path.abspath(c) != os.path.abspath(out)
			s = guaca.c2asm( open(c).read(), {}, [], includes=includes, defines=defines )
			if out:
				print('saving:', out)
				open(out,'w').write(s)

	if not c:
		print('no .c input files')
		mklinux()
