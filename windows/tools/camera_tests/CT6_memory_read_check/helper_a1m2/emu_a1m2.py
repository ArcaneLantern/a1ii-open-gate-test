"""Run the built A1 II read-only helper in Unicorn against a model camera. Offline; no camera. (A1 II port, 2026-11-26)

  C:/Python313/python.exe -B emu_a1m2.py [--show]

helper_fx30/emu_fx30.py with this camera's model (same harness: helper/emu_built.py; the same coprocessor model: only a transfer of one
whole page, direction 0, into the allocated buffer is accepted). Cases, for both libraries (check and dump):
  stock        an A1 II with the 4.00 files and stock memory (NTSC stored records) -> every check same, verdict READY
  stock-pal    the same with the stored records a PAL camera computes               -> READY (the records are soft sites)
  applied      every design site holding its new bytes, the screen step and F16 included -> TARGET everywhere, verdict READY
  no-screen    the open-gate state without the screen step                          -> open-gate TARGET, screen words STOCK, READY
  no-meta      the encoder side without the MP4 header heights (N19)                -> its sites TARGET, the two heights STOCK, READY
  real-rows    the real-rows alternative (R5) in place of L5                        -> table/matrix TARGET, the four picture records OTHER
  a1           the A1 (ILCE-1) 4.00 files and coprocessor image (the same sensor)   -> identity DIFFERS, verdict NOT READY
  fx30         the FX30 6.01 files and coprocessor image                            -> identity DIFFERS, verdict NOT READY
  fx2          the FX2 1.01 files and coprocessor image                             -> identity DIFFERS, verdict NOT READY
  a7iv         the A7 IV 6.02 files and coprocessor image                           -> identity DIFFERS, verdict NOT READY
  no-reserve   a command line without the av-cam reservation                        -> av-cam.bin not read, NOT READY
  no-logs      (kit v3) a command line that names neither log                       -> dump: both logs "not read", no log mapping, READY
  log-header-bad (kit v3) the two log areas without their "RBUF" header             -> dump: NOT AS EXPECTED printed, data still copied, READY
  exists       a result file already present                                        -> nothing done
Every case of the dump build (kit v3) also checks its log part: the 256 KB kernel log and the camera core's two areas copied raw and
exactly, six read-only mappings all inside the two logs and all unmapped; the check build has no log part.
and the other way round, the published check libraries of the FX30, FX3, FX2, ZV-E1 and A7S III kits run on a stock A1 II: each must say NOT
READY (an A1 II owner might run one of those kits; their apply scripts start only after a READY check).
"""
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "helper"))
import emu_built as E  # noqa: E402
from unicorn import arm64_const as R  # noqa: E402

BASE = 0x108000
FACTS = json.loads((HERE / "a1m2_expected.json").read_text(encoding="utf8"))
DES = ROOT / "modding/designs"
CP_RANGE = (0xC0000, 0x2700000)                 # the widest of the kits' read ranges: a foreign helper is modelled too
RECS, REC = 0x24DBA14, 0x170


def ex(build, rel):
    return (ROOT / "work/extracted" / build / "0700_part_image/dev" / rel).read_bytes()


def design(name):
    return json.loads((DES / f"{name}.json").read_text(encoding="utf8"))


class Run(E.Run):
    """E.Run with this helper's coprocessor model: cp_image (bytes at 0x108000) and cp_ram {address: bytes} over zeros."""

    def on_import(self, uc, address, size, _):
        x = lambda n: uc.reg_read(getattr(R, "UC_ARM64_REG_X%d" % n))
        name, ret = self.imports.get(address), 0
        if name == "_Z9dmm_allocjPj":
            self.lib_calls.append(("alloc", x(0) & 0xFFFFFFFF))
            uc.mem_write(x(1), struct.pack("<I", E.BUF_HANDLE))
            ret = self.buf
        elif name == "_Z8dmm_freej":
            self.lib_calls.append(("free", x(0) & 0xFFFFFFFF))
        elif name == "sen_dma_transfer":
            direction, src, dst, n = x(0) & 0xFFFFFFFF, x(1), x(2), x(3) & 0xFFFFFFFF
            self.lib_calls.append(("transfer", direction, src, dst, n))
            if direction != 0 or dst != self.buf or n != 4096 or src & 0xFFF or not CP_RANGE[0] <= src < CP_RANGE[1]:
                self.bad = "a transfer that is not a read of one whole page in range: dir %d src %#x dst %#x size %d" % (direction, src, dst, n)
                uc.emu_stop()
                return
            page = bytearray(4096)
            img = self.cp["image"]
            if BASE <= src < BASE + len(img):
                chunk = img[src - BASE:src - BASE + 4096]
                page[:len(chunk)] = chunk
            for a, blob in self.cp["ram"].items():
                lo, hi = max(a, src), min(a + len(blob), src + 4096)
                if lo < hi:
                    page[lo - src:hi - src] = blob[lo - a:hi - a]
            va = next(v for v, off in self.map_phys.items() if v in self.maps and off <= self.buf < off + self.maps[v]) + self.buf % 4096
            uc.mem_write(va, bytes(page))
        else:
            self.bad = "call of an unexpected import %r" % name
            uc.emu_stop()
            return
        uc.reg_write(R.UC_ARM64_REG_X0, ret)
        uc.reg_write(R.UC_ARM64_REG_PC, uc.reg_read(R.UC_ARM64_REG_X30))

    def go(self):
        self.uc.reg_write(R.UC_ARM64_REG_SP, E.STACK - 0x1000)
        self.uc.reg_write(R.UC_ARM64_REG_X30, E.RET)
        self.uc.emu_start(self.ctor, E.RET, count=3_000_000_000)
        if not self.bad and self.uc.reg_read(R.UC_ARM64_REG_PC) != E.RET:
            self.bad = "the constructor did not return (pc %#x)" % self.uc.reg_read(R.UC_ARM64_REG_PC)
        return self


# kit v3: the dump build's two logs (a1m2read.c log_part). The kernel log buffer, and the camera core's log subsystem with its two areas.
KLOG, KLOG_N = 0x400040000, 0x40000
ULOG_LO, ULOG_SUB, ULOG_TOTAL = 0x40510F000, 0x40510FFC4, 0xB6738
CAMLOGS = (("camlog_last", 0x405150054, 0x2024), ("camlog_first", 0x40517209C, 0xA044))
LOG_CMDLINE = b"klog.addr=0x400040000 klog.size=0x40000 memrsv=0x01000000@0x405000000 "


def klog_bytes():
    return bytes((k * 31 + 7) & 0xFF for k in range(KLOG_N))


def camlog_text(name):
    line = b"[%s] CamCore: AIF0 out[3840x2560] > memsize[3840x2462]\r\nFW: S-Ele Refresh ng\r\n" % name.encode()
    return line


def ulog_blob(header_ok=True):
    """Physical 0x40510f000 up to the end of area 3: the subsystem header, each area's 0x24-byte header and some text in its data."""
    blob = bytearray(0x40517209C + 0xA044 - ULOG_LO)
    struct.pack_into("<III", blob, ULOG_SUB - ULOG_LO, 0x11223344, 3, ULOG_TOTAL)
    for name, phys, size in CAMLOGS:
        o = phys - ULOG_LO
        data_va = 0x05000000 + (phys + 0x24 - 0x405000000)              # the data address as the camera core sees it (any value: printed, not checked)
        magic = 0x46554252 if header_ok else 0
        struct.pack_into("<IIIIII", blob, o, magic, data_va, size - 0x24, 0x40, 0, data_va + 0x100)
        t = camlog_text(name)
        blob[o + 0x24:o + 0x24 + len(t)] = t
    return bytes(blob)


def model(build="a1m2_400", applied=False, screen=True, reserve=True, exists=False, enc="ogfile2560_hs_s_a1m2_v2", system="ntsc", sensor="ogsq_a1m2_v1",
          logs=True, log_header_ok=True):
    cp = bytearray(ex(build, "nflasha8/cpapp-b.bin"))
    av = bytearray(ex(build, "nflasha3/av-cam.bin"))
    libs = {n: ex(build, "nflasha15/lib" + n) for n in ("/libmpr.so", "/libsencore.so", "/libJiritsu.so")}
    lm = bytearray(libs["/libmpr.so"])
    og, oz, fl, sc = design(sensor), design("outsz2560_a1m2_v1"), design(enc), design("lcdfill_a1m2_v1")
    ram = {}
    if build == "a1m2_400":                      # the A1 II's RAM tables; a foreign body keeps its own image and zeros
        for m, sr in og["stored_records"].items():
            ram[RECS + sr["index"] * REC] = bytes.fromhex(sr[system]["design" if applied else "stock"])
        for g in oz["guards"]:
            ram[int(g["ram_address"], 16)] = bytes.fromhex(g["bytes"])
        for s in oz["sites"]:
            ram[int(s["ram_address"], 16)] = bytes.fromhex(s["new" if applied else "old"])
    if applied:
        for p in og["patches"]:
            a, new = int(p["addr"], 16), bytes.fromhex(p["new"])
            cp[a - BASE:a - BASE + len(new)] = new
        for p in fl["patches"]:
            o, new = int(p["file_off"], 16), bytes.fromhex(p["new"])
            (lm if p["binary"] == "libmpr.so" else av)[o:o + len(new)] = new
        if sensor == "ogsq_a1m2_v1":            # kit v2: the default (and test3) applies F16 with the squeeze design
            for s in design("fehold_a1m2_v1")["sites"]:
                a = int(s["ram_address"], 16)
                cp[a - BASE:a - BASE + 4] = bytes.fromhex(s["new"])
        if screen:
            for s in sc["sites"]:
                a = int(s["ram_address"], 16)
                cp[a - BASE:a - BASE + 4] = bytes.fromhex(s["new"])
    lm_at = 0x7F82D15000
    maps = b"".join(b"%x-%x r-xp 00000000 b3:0f 100 /usr/lib%s\n" % (a, a + ((len(libs[n]) + 0xFFF) & ~0xFFF), n.encode())
                    for n, a in (("/libsencore.so", 0x7F80000000), ("/libJiritsu.so", 0x7F81000000), ("/libmpr.so", lm_at)))
    files = E.tree()
    files["/proc/self/maps"] = maps
    files["/proc/meminfo"] = b"MemTotal: 1 kB\n"
    files["/dev/mem"] = b""
    files["/proc/cmdline"] = (b"console=ttyS0 " + (b"memrsv=0x01000000@0x401000000:ex " if reserve else b"") + (LOG_CMDLINE if logs else b"")
                              + b"warm.mode=2")
    for n, b in libs.items():
        files["/usr/lib" + n] = b
    dirs = {"/tmp_wbshd", "/proc", "/proc/self", "/sys/module/liro/parameters", "/log", "/usr/lib"}
    if exists:
        files[E.RESULT] = b"earlier result\n"
    phys = {FACTS["avcam_phys"]: bytes([0x5A]) * 0x1000 + bytes(av[0x1000:]),      # the first page is not as in the file on a camera (A7S III, 2026-11-21)
            E.BUF_PHYS & ~0xFFF: bytes(0x2000), KLOG: klog_bytes(), ULOG_LO: ulog_blob(log_header_ok)}
    own = {lm_at: bytes(lm)}
    return files, dirs, phys, {"image": bytes(cp), "ram": ram}, own


def run(lib, **kw):
    files, dirs, phys, cp, own = model(**kw)
    r = Run(lib, 22, files, dirs, phys=phys, cp=cp, own=own)      # level 22: the A7 IV harness's rules for a read-only helper that maps /dev/mem
    r.go()
    return r, r.writes.get(E.RESULT, b"").decode("utf8", "replace")


def paddr(v):
    """An address as the helper's putaddr prints it: 0x and whole bytes, leading zero bytes left out (at least one byte)."""
    b = v.to_bytes(8, "big")
    k = 0
    while k < 7 and not b[k]:
        k += 1
    return b"0x" + b[k:].hex().encode()


def log_problems(which, case, r):
    """Kit v3: the dump build copies the kernel log and the camera core's two log areas exactly, raw, through read-only mappings it
    unmaps again, only when the command line names them; the check build has no log part at all."""
    raw = r.writes.get(E.RESULT, b"")
    if which == "check":
        return ["the check build has a log part"] if b"== logs" in raw else []
    out = []
    if b"== logs: the main processor's kernel log and the camera core's print log\n" not in raw:
        return ["no log part in the dump"]
    if r.maps or r.fds:
        out.append("a mapping or descriptor left open: %s %s" % (r.maps, r.fds))
    # the mappings this part makes: those in the kernel log's 256 KB or in the 16 MB the log module reserves; each must lie inside the
    # kernel log or inside the subsystem header to the end of area 3
    log_maps = [(off, n) for off, n, prot, flags in r.map_log if KLOG <= off < KLOG + KLOG_N or 0x405000000 <= off < 0x406000000]
    if any(prot != 1 or flags != 1 for _, _, prot, flags in r.map_log):
        out.append("a mapping that is not read-only and shared")
    if any(not (off + n <= KLOG + KLOG_N if off < 0x405000000 else ULOG_LO <= off and off + n <= (0x40517209C + 0xA044 + 0xFFF) & ~0xFFF)
           for off, n in log_maps):
        out.append("a log mapping outside the two logs: %s" % [(hex(o), hex(n)) for o, n in log_maps])
    if case not in ("no-logs",) and len(log_maps) != 6:          # klog; the subsystem header; per area its header and its data
        out.append("log mappings: %s" % [(hex(o), hex(n)) for o, n in log_maps])
    ulog = ulog_blob(case != "log-header-bad")
    if case == "no-logs":
        for w in (b"!! the kernel command line does not name klog.addr=0x400040000 klog.size=0x40000; the kernel log is not read\n",
                  b"!! the kernel command line does not reserve memory as memrsv=0x01000000@0x405000000; the camera core's log is not read\n"):
            if w not in raw:
                out.append("missing %r" % w[:60])
        if log_maps:
            out.append("logs mapped although the command line does not name them")
        return out
    want = [b"== klog at 0x0400040000 raw 262144 bytes follow\n" + klog_bytes() + b"\n== klog end\n",
            b"camlog subsystem 0x040510ffc4 header 4433221103000000" + struct.pack("<I", ULOG_TOTAL).hex().encode() + b"  as expected\n"]
    for name, phys, size in CAMLOGS:
        o = phys - ULOG_LO
        hdr = ulog[o:o + 0x24].hex().encode()
        want.append(b"camlog area %s %s header %s" % (name.encode(), paddr(phys), hdr)
                    + (b"  NOT AS EXPECTED\n" if case == "log-header-bad" else b"  as expected, written up to 0x0100\n"))
        want.append(b"== %s at %s raw %d bytes follow\n" % (name.encode(), paddr(phys + 0x24), size - 0x24) + ulog[o + 0x24:o + size] + b"\n== %s end\n" % name.encode())
    for w in want:
        if w not in raw:
            out.append("log copy not exact: %r" % w[:70])
    if case == "stock" and b"CamCore: AIF0 out[3840x2560] > memsize[3840x2462]" not in raw:
        out.append("the camera core's lines are not in the result")
    return out


def main():
    ok = True
    screen_n = sum(1 for s in FACTS["cp_sites"] if s["name"].startswith("screen"))
    hard = [s for s in FACTS["cp_sites"] if not s["name"].startswith(("outsize_guard",))]
    for which in ("check", "dump"):
        lib = (HERE / f"libJit_a1m2_{which}.so").read_bytes()
        for case, kw, want in (("stock", {}, ("VERDICT READY", "STOCK")), ("stock-pal", {"system": "pal"}, ("VERDICT READY", "STOCK")),
                               ("applied", {"applied": True}, ("VERDICT READY", "TARGET")),
                               ("no-screen", {"applied": True, "screen": False}, ("VERDICT READY", "TARGET")),
                               ("no-meta", {"applied": True, "enc": "ogfile2560_hs_s_a1m2_v1"}, ("VERDICT READY", "TARGET")),
                               ("real-rows", {"applied": True, "sensor": "ogh2880_a1m2_v1"}, ("TARGET",)),
                               ("a1", {"build": "a1_400"}, ("VERDICT NOT READY", "DIFFERS from the 4.00 update")),
                               ("fx30", {"build": "fx30_601"}, ("VERDICT NOT READY", "DIFFERS from the 4.00 update")),
                               ("fx2", {"build": "fx2_101"}, ("VERDICT NOT READY", "DIFFERS from the 4.00 update")),
                               ("a7iv", {"build": "a7iv_602"}, ("VERDICT NOT READY", "DIFFERS from the 4.00 update")),
                               ("no-reserve", {"reserve": False}, ("VERDICT NOT READY", "av-cam.bin is not read")),
                               ("no-logs", {"logs": False}, ("VERDICT READY",)), ("log-header-bad", {"log_header_ok": False}, ("VERDICT READY",)),
                               ("exists", {"exists": True}, ())):
            r, text = run(lib, **kw)
            problems = []
            if r.bad:
                problems.append("stopped: " + r.bad)
            if set(r.writes) - {E.RESULT}:
                problems.append("wrote other files: %s" % sorted(set(r.writes) - {E.RESULT}))
            if any(c[0] == "transfer" and c[1] != 0 for c in r.lib_calls):
                problems.append("a transfer towards the coprocessor")
            if case == "exists":
                if r.writes or r.lib_calls:
                    problems.append("did something although a result existed")
            else:
                problems += ["missing %r" % w for w in want if w not in text]
                if "== done" not in text:
                    problems.append("result not complete")
                if case == "stock" and ("OTHER" in text.replace("OTHER (not counted", "") or "DIFFERS" in text or "!!" in text.split("== identity")[1]):
                    problems.append("a stock camera is not reported as all stock")
                if case == "stock-pal":
                    recs = [ln for ln in text.split("\n") if ln.startswith("site stored_record_")]
                    if len(recs) != 4 or not all(ln.endswith("OTHER (not counted: filled at run time)") for ln in recs):
                        problems.append("PAL records: %s" % [ln[-45:] for ln in recs])
                    if "DIFFERS" in text or "OTHER  \n" in text:
                        problems.append("a PAL camera's hard sites not all stock")
                if case == "applied" and text.count("TARGET") < len(hard) + FACTS["lm_sites"] + FACTS["av_sites"]:
                    problems.append("not every site reported TARGET: %d" % text.count("TARGET"))
                if case == "no-screen":
                    st = sum(1 for ln in text.split("\n") if ln.startswith("site screen") and ln.endswith("  STOCK"))
                    if st != screen_n or text.count("TARGET") < len(hard) - screen_n + FACTS["lm_sites"] + FACTS["av_sites"]:
                        problems.append("no-screen: %d screen words stock (want %d)" % (st, screen_n))
                if case == "no-meta":                      # N19: its sites TARGET, the two header heights STOCK
                    lm = [ln for ln in text.split("\n") if ln.startswith("lm ")]
                    if sum(ln.endswith("TARGET") for ln in lm) != 4 or sum(ln.endswith("STOCK") for ln in lm) != 2:
                        problems.append("no-meta: libmpr lines %s" % lm)
                if case == "real-rows":                    # R5 in place of L5: tables and matrix TARGET, the four picture records OTHER
                    sn = [ln for ln in text.split("\n") if ln.startswith("site record_")]
                    tm = [ln for ln in text.split("\n") if ln.startswith(("site crop", "site window", "site pdaf", "site lc ", "site readout", "site geometry", "site matrix_"))]
                    if len(sn) != 4 or not all("OTHER" in ln for ln in sn) or len(tm) != 9 or not all(ln.endswith("  TARGET") for ln in tm):
                        problems.append("real-rows sensor sites: %s" % (sn + tm))
                if case in ("stock", "applied"):           # the sensor design's thirteen sites are hard
                    sn = [ln for ln in text.split("\n") if ln.startswith(("site crop", "site window", "site pdaf", "site lc ", "site readout", "site geometry", "site record_", "site matrix_"))]
                    if len(sn) != 13 or not all(ln.endswith("  " + ("TARGET" if case == "applied" else "STOCK")) for ln in sn):
                        problems.append("sensor sites: %s" % sn)
                if which == "dump" and case == "stock" and text.count("cppage ") != sum(k for _, _, k in FACTS["dump_ranges"]):
                    problems.append("dump pages: %d" % text.count("cppage "))
                problems += log_problems(which, case, r)
            n_tr = sum(1 for c in r.lib_calls if c[0] == "transfer")
            print(f"{which:5} {case:10} {'ok' if not problems else 'FAILED'}  result {len(text):7} bytes, {n_tr:3} page reads  {'; '.join(problems)}")
            ok &= not problems
            if "--show" in sys.argv and case == "stock":
                print("\n".join(ln[:150] for ln in text.split("== identity")[1].splitlines()[:80]))
    # ---- the other kits' check libraries on an A1 II
    for kit, path, verdict in (("FX30 kit", HERE.parent / "helper_fx30/libJit_fx30_check.so", "DIFFERS from the 6.01 update"),
                               ("FX3 kit", HERE.parent / "helper_fx3/libJit_fx3_check.so", "DIFFERS from the 7.02 update"),
                               ("FX2 kit", HERE.parent / "helper_fx2/libJit_fx2_check.so", "DIFFERS from the 1.01 update"),
                               ("ZV-E1 kit", HERE.parent / "helper_zv/libJit_zv_check.so", "DIFFERS from the 2.02 update"),
                               ("A7S III kit", HERE.parent / "helper_s3/libJit_s3_check.so", "DIFFERS from the 5.01 update")):
        if not path.is_file():
            print(f"foreign {kit}: library not here, skipped")
            continue
        r, text = run(path.read_bytes())
        good = not r.bad and "VERDICT NOT READY" in text and verdict in text and not (set(r.writes) - {E.RESULT})
        print(f"foreign {kit:12} on a stock A1 II: {'ok, NOT READY' if good else 'FAILED'}  {r.bad or ''}")
        ok &= good
    print("ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
