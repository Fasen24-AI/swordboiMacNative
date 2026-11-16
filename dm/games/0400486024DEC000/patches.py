# The Legend of Zelda: Ocarina of Time (0400486024DEC000): the rewriter's patches of this game's own code. dm/tools/patch_nso.py loads every profile's patches.py;
# FRAME_STEP and MATCH_FRAME_STEP as described there ("Registered patches"). Patches of Nintendo SDK module builds are in dm/tools/sdk_patches.py
from nso_asm import ADRP, B

# The game's frame ratio. Once a frame the function at main+0x6e6be0 (v131072) divides its base rate (60.0, or 30.0 while bit 0 of [x21+0x24f] is set) by the int frame rate at
# [x21+0x2c8] (fdiv s8,s1,s0 at +0xe4) and hands the result to the time object (main+0x3b4e300: ratio at +0x10, 1 / ratio at +0x14, round(60 / ratio) at +0x1c), which the game
# steps by; the frame's own time never enters it, so a frame that takes two vsyncs at rate 60 plays at half speed. The stub gives the ratio the host's step instead: step × base / 60
# (the division's value when the host keeps frames 60 / rate vsyncs), and counts the vsyncs stepped. Until the host has decided a step, and at fps_target 0, the division runs.
# s0 and x16 / x17 are free there (s0 is written again on every path before it is read; the function uses neither x16 nor x17); s1 keeps the base rate.
# Lichii (a GPL emulator; only the fact was taken) found the division (its notes: main+0x6E6CC4, 60 / [x21+0x2C8])
def frame_step(ctx):
    here, emit, fs_site, fs_put, FS_STATE_OFF, base = ctx.here, ctx.emit, ctx.site, ctx.put, ctx.state, ctx.base
    site = base + 0xe4
    fs_site(site, '2818201e')   # fdiv s8,s1,s0
    start = here(); emit(ADRP(16, here(), FS_STATE_OFF))
    for w in (0xb9400211,   # ldr w17,[x16]          target fps (0 = off)
              0x340001b1,   # cbz w17,orig (+13)
              0xb9402211,   # ldr w17,[x16,#0x20]    step in vsyncs
              0x34000171,   # cbz w17,orig (+11)     not decided yet
              0x1e230220,   # ucvtf s0,w17
              0xf9401a10,   # ldr x16,[x16,#0x30]
              0x8b110210):  # add x16,x16,x17
        emit(w)
    emit(ADRP(17, here(), FS_STATE_OFF))
    for w in (0xf9001a30,   # str x16,[x17,#0x30]    vsyncs stepped
              0x1e210808,   # fmul s8,s0,s1          step × base rate
              0x52a84e10,   # mov w16,#0x42700000    60.0
              0x1e270200,   # fmov s0,w16
              0x1e201908):  # fdiv s8,s8,s0          / 60
        emit(w)
    emit(B(here(), site + 4))
    emit(0x1e201828); emit(B(here(), site + 4))   # orig: fdiv s8,s1,s0; back
    fs_put(site, [B(site, start)], 'frame ratio: the host\'s step × base rate / 60 instead of base rate / the game\'s frame rate (state page target fps; 0 = the game\'s ratio)')
    dynamic_resolution(ctx)
    render_scale(ctx)
    if base == 0x6e6be0: native_output(ctx)   # v131072's main (the only build the crop sites are known for)
    if base == 0x6e6be0: render_size(ctx)   # v131072's main (the only build the render-size sites are known for)
    if base == 0x6e6be0: ultrawide(ctx)   # v131072's main (the only build the ultrawide sites are known for)

# The game's dynamic resolution (game__gfx__DynamicResolutionParam: LoadThreshold, ReduceCounterMax, IncreaseCounterMax and a list of levels, each a ResolutionReduceScale and a
# Priority; on v131072 levels 0..9 at 0.75..0.333 of 2048x1152, 1536x864 to 683x384). Its update (main+0x805aa0) reads the frame's GPU load (about 0.2 ms a unit) into +0x8, subtracts
# its small model of the fixed costs and divides the rest by the square of the current scale: it takes the rest of the frame's cost to grow with the pixel count, as on the Switch 2
# its constants were tuned for. The level function (main+0x8065e0) adds that back times each level's scale squared and returns the best level under the threshold (+0x10, 83 = about
# 16.4 ms). On Apple GPUs this game's cost hardly depends on the resolution (mesh, compute and the upscaler's fixed 2048x1152 dominate): 683x384 cost 14.3 ms and 1536x864 14.7 ms on
# an M4 Pro, yet at 683x384 the extrapolation put 1536x864 at about 300 units against the 83 it allows, so the controller sat at its floor for good (game note, Dynamic resolution).
# The stub replaces the level function. With DM_DYNAMIC_RESOLUTION 0 (the default; state +0x40 0) it returns 0: full resolution. With 1 it climbs on what was measured at each
# level, with no model of how the cost grows: one level down when the load (+0x8) has been over the threshold for 8 calls in a row, and that level is marked as not fitting; one level
# up when the load fits and the level above was never measured, fitted when it was last measured, or was measured more than 600 calls (about 10 s) ago; else the current level
# (+0x174). Nothing is decided or recorded until a level has held 8 calls: the load is read a few frames late, so before that it may be the previous level's. The 8 calls over in a
# row keep a single slow frame, or the first frames at a new size (its render targets), from marking a level that fits (on the full library at level 1: one burst to 90 against loads
# of 77-80 at levels 2 and 1). The game's counters still pace the steps (down after ReduceCounterMax frames, up after IncreaseCounterMax); its level count (+0x1a0) is the floor.
# The memory is in the state page: +0x200 calls, +0x204 the last call's level, +0x208 calls at it, +0x20c calls over in a row, +0x210 the load measured at each level (16 floats),
# +0x250 the call it was measured at (0 = never). Run against a model of the update (a level moves after the stub asked 5 times up or 2 times down; the load two frames late): a load
# of 70 at every level climbs from the floor to full size in 9 steps, as does Ocarina's measured 72-80 with a spike every 37 frames and a burst after each change; a load that grows
# with the pixel count settles at the highest level that fits and tries the one above once per 600 calls; a scene that gets lighter climbs again, a heavier one steps down.
# The function is a leaf: x2..x11, x16, x17 and s0..s2 are free, w0 its only result (the original also stores its predicted cost at +0x18, which only it and the update's own
# decision read). The update's fingerprint is required too: +0x8 and +0x174 are its fields
drs_controller = (   # drs_stub.s, assembled with clang; x0 the controller, x16 the state page (the ADRP before it)
    0xb9404211, 0x35000071, 0x2a1f03e0, 0xd65f03c0,                                                   # off (state +0x40 0): level 0
    0xbd400800, 0xbd401001, 0xb9417402, 0xb941a003, 0x7100005f, 0x1a9fa042, 0x528001e9, 0x6b09005f,   # load, threshold, level (0..15), count
    0x1a89d042, 0xb9420204, 0x11000484, 0xb9020204, 0xb9420605, 0xb9420a06, 0x6b0200bf, 0x1a8617e6,   # calls + 1; calls at this level
    0xb9020602, 0xb9020a06, 0x35000046, 0xb9020e1f, 0x91084207, 0x91094208, 0x710020df, 0x5400040b,   # a new level: none over; under 8 calls: stay
    0x1e212000, 0x540001ad, 0xb9420e0b, 0x1100056b, 0xb9020e0b, 0x7100217f, 0x5400032b,               # over: under 8 in a row, stay
    0xbc2258e0, 0xb8225904, 0x51000469, 0x1100044a, 0x6b09015f, 0x1a89d140, 0xd65f03c0,               # 8 in a row: record it, down one (to the floor)
    0xb9020e1f, 0xbc2258e0, 0xb8225904, 0x34000182, 0x51000449, 0xb869590a, 0x340000ea, 0x4b0a008a,   # fits: record it; at 0 stay; the level above's record
    0x7109615f, 0x54000088, 0xbc6958e2, 0x1e212040, 0x540000aa, 0x2a0903e0, 0xd65f03c0,               # never, stale or fitting: up one
    0x2a1f03e0, 0xd65f03c0, 0x2a0203e0, 0xd65f03c0)                                                   # 0; or stay
def dynamic_resolution(ctx):
    here, emit, fs_site, fs_put, FS_STATE_OFF = ctx.here, ctx.emit, ctx.site, ctx.put, ctx.state
    site = ctx.others.get('dynamic resolution')
    if site is None or ctx.others.get('dynamic resolution update') is None: return   # not both found in this build (a red line from the locator): the game's own dynamic resolution
    fs_site(site, '017c40bd')   # ldr s1,[x0,#0x7c]
    start = here(); emit(ADRP(16, here(), FS_STATE_OFF))
    for w in (0xb9401211,   # ldr w17,[x16,#0x10]   the host render scale's bits (1.0 = the game's own size, written by the loader when unset)
              0x34000091,   # cbz w17,+4            none written: as below
              0x52a7f002,   # mov w2,#0x3f800000    1.0
              0x6b02023f,   # cmp w17,w2
              0x54000061):  # b.ne +3               a fixed render scale (render_scale below): level 0, the game's own size, which the scale then multiplies
        emit(w)
    for w in drs_controller: emit(w)
    fs_put(site, [B(site, start)], 'dynamic resolution level: 0 (full resolution) also under a render scale below 1.0, or with state +0x40 (DM_DYNAMIC_RESOLUTION) a climb on the load measured at each level')
    ctx.capabilities.add('DYNAMIC_RESOLUTION')

# Native output (DM_OUTPUT=native, the launcher's Output; v131072 only, guarded by the matched frame-step function's place): the game draws its picture into 80 % of the output
# and the system scales that up, the console's own frame. The crop is set in main+0x650380's function: crop = the base size ([entry+0x64], ints) times a float pair per mode and
# level, 0.8 here, read from [obj+0xf0 + mode * 0x208 + level * 0x60 + (signed byte [obj+0x54a]) * 8 + 0x1e4 / +0x1e8]; each side is clamped to the size from main+0x112c5e0
# and stored through main+0x1087f40, which main+0x650538 later reads for nvnWindowSetCrop (called from main+0x11e7b74). The 0.8 is in code, not in
# ModelSceneExtensionParam. Found by watching the crop object's size field: one store, 3024x1702 -> 2419x1361, pc main+0x1087f64, lr main+0x650604.
# The stubs skip the two multiplies when state +0x44 is 1, so the crop is the full base size and the picture, the 3D and its depth are the full output size. x16 is free at
# both sites: a call (bl main+0x112c5e0) follows within three instructions and nothing between reads x16
def native_output(ctx):
    here, emit, fs_site, fs_put, ST = ctx.here, ctx.emit, ctx.site, ctx.put, ctx.state
    for site, orig in ((0x6505c4, 0x1e200840), (0x6505d4, 0x1e200820)):   # fmul s0,s2,s0 (width) / fmul s0,s1,s0 (height)
        fs_site(site, orig.to_bytes(4, 'little').hex())
        start = here(); emit(ADRP(16, here(), ST))
        emit(0xb9404610)   # ldr w16,[x16,#0x44]   1 = native output
        emit(0x35000050)   # cbnz w16,+8           skip the multiply
        emit(orig)         # the original multiply: the game's 80 %
        emit(B(here(), site + 4))
        fs_put(site, [B(site, start)], 'native output: the crop multiply skipped when state +0x44 is set (DM_OUTPUT=native), so the picture is the full output size')
    ctx.capabilities.add('NATIVE_OUTPUT')
# Render size (DM_RENDER_SIZE, the launcher's Resolution; v131072 only, guarded by the matched frame-step function's place): the game sizes its docked output and render
# targets from fixed 2560x1440 constants (the sites upstream PR #1460 found for its ultrawide cuts); these stubs take the state page's size instead (+0x38: u32 width,
# u32 height, read as one x = width | height << 32; 0 = the game's own). Each keeps the original instructions for size 0. Handheld (1920x1080) is left alone.
#   main+0x1202ee0  the graphics setup config's output size (swap chain), x8 = 2560 | 1440 << 32 (mov/movk), stored at [x21+0x14]
#   main+0x31f39f4  the docked render size, the same pattern, stored at [x19+0xb68]
#   main+0x112c604  the display mode's output size, read from the table at main+0x3f58540: its 2560x1440 entry becomes the size
#   main+0xecbc80 / +0xecbcb4  the float copies of the output width (w9 = 2560.0f) and height (w8 = 1440.0f) in the same object's init
# The float stubs convert through s31, saved below sp and restored (no FP register is known free there)
NOP = 0xd503201f
def render_size(ctx):
    here, emit, fs_site, fs_put, ST = ctx.here, ctx.emit, ctx.site, ctx.put, ctx.state
    for site in (0x1202ee0, 0x31f39f4):   # mov x8,#0xa00; movk x8,#0x5a0,lsl #32
        fs_site(site, '084081d208b4c0f2')
        start = here(); emit(ADRP(8, here(), ST))
        for w in (0xf9401d08,   # ldr x8,[x8,#0x38]       width | height << 32
                  0xb5000068,   # cbnz x8,+12             set: keep it
                  0xd2814008,   # mov x8,#0xa00           2560
                  0xf2c0b408):  # movk x8,#0x5a0,lsl #32  1440
            emit(w)
        emit(B(here(), site + 8))
        fs_put(site, [B(site, start), NOP], 'render size: %s from the state page (DM_RENDER_SIZE), 2560x1440 when it is 0' % ('output (swap chain) size' if site == 0x1202ee0 else 'docked render size'))
    site = 0x112c604   # ldr x8,[x9,x8,lsl #3]  the display mode's output size from the table
    fs_site(site, '287968f8')
    start = here(); emit(0xf8687928)          # ldr x8,[x9,x8,lsl #3]
    emit(ADRP(16, here(), ST))
    for w in (0xf9401e10,   # ldr x16,[x16,#0x38]
              0xb40000b0,   # cbz x16,+20            not set: the table's entry
              0xd2814011,   # mov x17,#0xa00
              0xf2c0b411,   # movk x17,#0x5a0,lsl #32
              0xeb11011f,   # cmp x8,x17             the 2560x1440 entry (docked)
              0x9a880208):  # csel x8,x16,x8,eq
        emit(w)
    emit(B(here(), site + 4))
    fs_put(site, [B(site, start)], 'render size: the display mode\'s 2560x1440 output entry becomes the state page\'s size (DM_RENDER_SIZE)')
    for site, orig, ldr, cbz, fmov, name in ((0xecbc80, 0x52a8a409, 0xb9403929, 0x340000c9, 0x1e2603e9, 'width'),    # mov w9,#0x45200000 (2560.0f)
                                             (0xecbcb4, 0x52a89688, 0xb9403d08, 0x340000c8, 0x1e2603e8, 'height')):  # mov w8,#0x44b40000 (1440.0f)
        r = 9 if name == 'width' else 8
        fs_site(site, orig.to_bytes(4, 'little').hex())
        start = here(); emit(ADRP(r, here(), ST))
        for w in (ldr,          # ldr wR,[xR,#0x38 / 0x3c]
                  cbz,          # cbz wR,orig (+24)
                  0xfc1f0fff,   # str d31,[sp,#-16]!
                  0x1e23001f | r << 5,   # ucvtf s31,wR
                  fmov,         # fmov wR,s31
                  0xfc4107ff):  # ldr d31,[sp],#16
            emit(w)
        emit(B(here(), site + 4))
        emit(orig); emit(B(here(), site + 4))
        fs_put(site, [B(site, start)], 'render size: output %s as a float from the state page (DM_RENDER_SIZE)' % name)
    ctx.capabilities.add('RENDER_SIZE')

# Ultrawide (DM_RENDER_SIZE wider than 16:9, e.g. 3440x1440; v131072 only). Ported from craftycorvid/oot-mod (MIT, https://github.com/craftycorvid/oot-mod: build.py's
# hooks and picture size for main E0F3CCFAF50065AE), with its constants read from the state page instead of fixed in the code, so a 16:9 size leaves the game as it is:
#   +0x800 f32 target aspect (0 = off), +0x804 f32 HUD squeeze (16/9) / target, +0x808 f32 movie margin (1 - squeeze) / 2, +0x80c f32 speech bubble half width 1920 / squeeze,
#   +0x810 u64 the scene size (3/4 of the picture, width | height << 32; 0 = the game's 1920x1080), +0x818 f32 the HUD edge shift (1 - squeeze; 0 keeps the HUD centred),
#   +0x81c u32 entries in the HUD anchor table, +0x820 the table: 16 entries of {u64 screen vtable (runtime address), f32 side (-1 left edge, +1 right edge), pad},
#   +0x9f0 f32 the movies' height growth on each side (DM_UW_MOVIE_FILL; 0 = in the centre 16:9),
#   +0xa00 u32 1 records the screens drawn with the layout ortho, +0xa04 u32 how many, +0xa08 32 entries of {u64 screen, u64 vtable} (DM_UW_HUD_RECORD, to find a screen's vtable).
#   Written by the loader (dm/host/loader.c) for a wide DM_RENDER_SIZE. Not +0x200: the dynamic-resolution controller's memory is +0x200..+0x290
# The picture itself comes from render_size above (swap chain, docked render size, display mode, float output size). The hooks:
#   - every 16:9 sead::PerspectiveProjection (doUpdateMatrix main+0x3485cc0 and its inlined copies +0x4f1e8, +0x23b9a8, +0x33b82c) takes the target aspect and writes it back
#     to mAspect (+0xb0), so culling sees the wider view; the render view's w / h aspect for shaders (+0x25d76c) the same. Other aspects (cubemaps, 1:1) are left alone
#   - full-screen 2D (the 3840x2160 layout ortho, +0x774368) is squeezed into the centre 16:9, except the screens that redraw a capture of the whole frame or fade it; the HUD
#     screens of the anchor table (the hearts', the minimap's: loader.c DM_UW_HUD_DEFAULT) then move to the screen's edges (DM_UW_HUD_EDGES)
#   - pre-rendered movies get the centre 16:9 viewport, or fill the width with their top and bottom cut (DM_UW_MOVIE_FILL; +0x3b5c758); NPC speech bubbles' layout x is
#     divided by the squeeze (+0x20c2b0)
#   - the graphics allocator's render-target pool is doubled (+0xc2a36c, as Lichii PR #976's "Texture Pool x2"): the wider targets ran the stock pool out and the game froze
#   - the scene its upscaler takes in (+0x31f3a00, 1920x1080) is 3/4 of the picture
# Scratch registers are those craftycorvid's hooks use (overwritten by the game right after each site), plus x16 / x17 saved around the pool hook
_uw = 0x800
_uw_full_frame_screens = (0x4bed098, 0x4be4fb0, 0x4be7b30, 0x4be61c8)   # vtables: L/R item menu, pause / system menu backgrounds, area loading fade, cutscene fades
def _uw_f32(x): import struct; return struct.unpack('<I', struct.pack('<f', x))[0]
def _uw_movz(wd, imm): return 0x52800000 | (imm & 0xffff) << 5 | wd
def _uw_movk16(wd, imm): return 0x72a00000 | (imm & 0xffff) << 5 | wd
def _uw_fmov_sw(sd, wn): return 0x1e270000 | wn << 5 | sd
def _uw_fmov_ws(wd, sn): return 0x1e260000 | sn << 5 | wd
def _uw_fmov_ss(sd, sn): return 0x1e204000 | sn << 5 | sd
def _uw_fsub(sd, sn, sm): return 0x1e203800 | sm << 16 | sn << 5 | sd
def _uw_fadd(sd, sn, sm): return 0x1e202800 | sm << 16 | sn << 5 | sd
def _uw_fmul(sd, sn, sm): return 0x1e200800 | sm << 16 | sn << 5 | sd
def _uw_fabs(sd, sn): return 0x1e20c000 | sn << 5 | sd
def _uw_fcmp(sn, sm): return 0x1e202000 | sm << 16 | sn << 5
def _uw_fcmp0(sn): return 0x1e202008 | sn << 5
def _uw_ldr_s(st, xn, off): return 0xbd400000 | (off // 4) << 10 | xn << 5 | st
def _uw_str_s(st, xn, off): return 0xbd000000 | (off // 4) << 10 | xn << 5 | st
def _uw_ldr_w(wt, xn, off): return 0xb9400000 | (off // 4) << 10 | xn << 5 | wt
def _uw_ldr_x(xt, xn, off): return 0xf9400000 | (off // 8) << 10 | xn << 5 | xt
def _uw_ldp_s(s1, s2, xn, off): return 0x2d400000 | ((off // 4) & 0x7f) << 15 | s2 << 10 | xn << 5 | s1
def _uw_ldp_q(q1, q2, xn, off): return 0xad400000 | ((off // 16) & 0x7f) << 15 | q2 << 10 | xn << 5 | q1
def _uw_ldp_x(x1, x2, xn, off): return 0xa9400000 | ((off // 8) & 0x7f) << 15 | x2 << 10 | xn << 5 | x1
def _uw_cmp_w(wn, wm): return 0x6b00001f | wm << 16 | wn << 5
def _uw_cmp_x(xn, xm): return 0xeb00001f | xm << 16 | xn << 5
def _uw_sub_x(xd, xn, imm): return 0xd1000000 | imm << 10 | xn << 5 | xd
def _uw_add_x(xd, xn, imm): return 0x91000000 | imm << 10 | xn << 5 | xd
def _uw_umov_s1(wd, vn): return 0x0e0c3c00 | vn << 5 | wd   # mov wd, vn.s[1]
def _uw_and_abs(wd, wn): return 0x12007800 | wn << 5 | wd   # and wd, wn, #0x7fffffff
def _uw_dup_4s(vd, wn): return 0x4e040c00 | wn << 5 | vd
def _uw_fmul_4s(vd, vn, vm): return 0x6e20dc00 | vm << 16 | vn << 5 | vd
def _uw_scvtf_sw(sd, wn): return 0x1e220000 | wn << 5 | sd
def _uw_fdiv(sd, sn, sm): return 0x1e201800 | sm << 16 | sn << 5 | sd
def _uw_cmp_w_imm(wn, imm): return 0x7100001f | imm << 10 | wn << 5
def _uw_mov_w(wd, wm): return 0x2a0003e0 | wm << 16 | wd
def _uw_ldr_x_post(xt, xn, imm): return 0xf8400400 | (imm & 0x1ff) << 12 | xn << 5 | xt
def _uw_subs_w(wd, wn, imm): return 0x71000000 | imm << 10 | wn << 5 | wd
def _uw_add_w(wd, wn, imm): return 0x11000000 | imm << 10 | wn << 5 | wd
def _uw_stp_x(x1, x2, xn, off): return 0xa9000000 | ((off // 8) & 0x7f) << 15 | x2 << 10 | xn << 5 | x1
def _uw_str_w(wt, xn, off): return 0xb9000000 | (off // 4) << 10 | xn << 5 | wt
def _uw_ldur_s(st, xn, imm): return 0xbc400000 | (imm & 0x1ff) << 12 | xn << 5 | st
def _uw_dup_s0(sd, vn): return 0x5e040400 | vn << 5 | sd   # mov sd, vn.s[0]
def _uw_ins_s0(vd, vn): return 0x6e040400 | vn << 5 | vd   # mov vd.s[0], vn.s[0]
# Branches inside a stub body are written as ('b.cond' | 'cbz' | 'cbnz', cond or register, label) and labels as ('label', name); 'end' is the branch back.
# An ADRP is ('adrp', register, target). _uw_stub resolves them against the body's place and emits it, then the branch back
def _uw_stub(ctx, site, original, body, why):
    import struct
    ctx.site(site, b''.join(struct.pack('<I', w) for w in original).hex())
    start = ctx.here(); labels, pos = {}, 0
    for w in body:
        if isinstance(w, tuple) and w[0] == 'label': labels[w[1]] = pos
        else: pos += 1
    labels['end'] = pos
    words = []
    for w in body:
        if isinstance(w, tuple):
            if w[0] == 'label': continue
            pc = start + 4 * len(words)
            if w[0] == 'adrp': words.append(ADRP(w[1], pc, w[2])); continue
            off = ((start + 4 * labels[w[2]]) - pc) >> 2
            if w[0] == 'b.cond': words.append(0x54000000 | (off & 0x7ffff) << 5 | w[1])
            elif w[0] == 'cbz': words.append(0x34000000 | (off & 0x7ffff) << 5 | w[1])
            elif w[0] == 'cbnz': words.append(0x35000000 | (off & 0x7ffff) << 5 | w[1])
            elif w[0] == 'cbnz_x': words.append(0xb5000000 | (off & 0x7ffff) << 5 | w[1])
            elif w[0] == 'b': words.append(0x14000000 | (off & 0x3ffffff))
            else: raise ValueError(w)
        else: words.append(w)
    for w in words: ctx.emit(w)
    ctx.emit(B(ctx.here(), site + 4 * len(original)))
    ctx.put(site, [B(site, start)] + [NOP] * (len(original) - 1), why)
_c_eq, _c_ne, _c_hs, _c_pl = 0, 1, 2, 5
def _uw_load_f32(wt, st, value):
    bits = _uw_f32(value)
    return [_uw_movz(wt, bits), _uw_movk16(wt, bits >> 16), _uw_fmov_sw(st, wt)]
# if |sa - 16/9| < 0.01 and the state's target is set: sa = target (and store it to [writeback, #0xb0]); b.pl leaves NaN alone
def _uw_fix_aspect(ST, sa, wt, sp, sq, writeback=None):
    return (_uw_load_f32(wt, sp, 16 / 9) + [_uw_fsub(sp, sa, sp), _uw_fabs(sp, sp)] + _uw_load_f32(wt, sq, 0.01)
            + [_uw_fcmp(sp, sq), ('b.cond', _c_pl, 'end'), ('adrp', wt, ST), _uw_ldr_s(sp, wt, (ST & 0xfff) + _uw), _uw_fcmp0(sp), ('b.cond', _c_eq, 'end'),
               _uw_fmov_ss(sa, sp)] + ([_uw_str_s(sa, writeback, 0xb0)] if writeback is not None else []))
def ultrawide(ctx):
    ST = ctx.state
    assert ST % 0x1000 == 0   # the loads below take the state page's offset in their immediate
    # the four projection builders: ldp s0, sN, [xB, #0xac] (fovy, aspect)
    for site, orig, base, sa, wt, sp, sq in ((0x3485cc0, 0x2d558400, 0, 1, 16, 16, 17), (0x004f1e8, 0x2d558ea0, 21, 3, 9, 4, 5),
                                             (0x023b9a8, 0x2d558c00, 0, 3, 9, 4, 5), (0x033b82c, 0x2d558440, 2, 1, 9, 2, 3)):
        _uw_stub(ctx, site, [orig], [_uw_ldp_s(0, sa, base, 0xac)] + _uw_fix_aspect(ST, sa, wt, sp, sq, writeback=base),
                 'ultrawide: a 16:9 camera projection takes the state page\'s target aspect (DM_RENDER_SIZE wider than 16:9), written back to mAspect')
    # the render view's aspect for shaders: scvtf s1, w21; fdiv s1, s1, s2
    _uw_stub(ctx, 0x025d76c, [0x1e2202a1, 0x1e221821], [_uw_scvtf_sw(1, 21), _uw_fdiv(1, 1, 2)] + _uw_fix_aspect(ST, 1, 16, 16, 17),
             'ultrawide: the render view\'s 16:9 aspect takes the target aspect')
    # full-screen 2D: after ldp q1, q4, [x2] (the projection's first two vectors, its x and y columns; x0 = canvas), the 3840x2160 layout ortho's x column scaled by the squeeze,
    # unless the canvas's screen covers the frame. The projection is set when a screen is made, not every frame
    # x10..x17 and v16..v18 are free here: the function is a leaf that uses none of them after the site (v16..v19 are written next), and its callers take x9..x17 as clobbered.
    # Then each screen in the anchor table (state +0x820, by vtable) moves to its side: the x translation (element 0 of the fourth vector, q6, loaded before the site: the
    # vectors are the matrix's columns, so q1's element 3 is w's x term) += side * edge shift, so the centre 16:9 area's edge meets the
    # screen's (the hearts on the left, the minimap on the right); other screens stay centred. DM_UW_HUD_RECORD lists the screens drawn so (state +0xa00)
    body = [_uw_ldp_q(1, 4, 2, 0), _uw_fmov_ws(16, 1), _uw_movz(17, _uw_f32(2 / 3840)), _uw_movk16(17, _uw_f32(2 / 3840) >> 16), _uw_cmp_w(16, 17), ('b.cond', _c_ne, 'end'),
            _uw_umov_s1(16, 4), _uw_and_abs(16, 16), _uw_movz(17, _uw_f32(2 / 2160)), _uw_movk16(17, _uw_f32(2 / 2160) >> 16), _uw_cmp_w(16, 17), ('b.cond', _c_ne, 'end'),
            _uw_sub_x(15, 0, 0x1b8), _uw_ldr_x(16, 15, 0)]   # the UI screen object holding the canvas at +0x1b8 (x15): its vtable (x16)
    for vt in _uw_full_frame_screens: body += [('adrp', 17, vt), _uw_add_x(17, 17, vt & 0xfff), _uw_cmp_x(16, 17), ('b.cond', _c_eq, 'end')]
    o = (ST & 0xfff) + _uw
    body += [('adrp', 14, ST),
             _uw_ldr_w(12, 14, o + 0x200), ('cbz', 12, 'squeeze'), _uw_ldr_w(12, 14, o + 0x204), _uw_cmp_w_imm(12, 32), ('b.cond', _c_hs, 'squeeze'),
             _uw_add_x(11, 14, o + 0x208), _uw_mov_w(13, 12),
             ('label', 'scan'), ('cbz', 13, 'new'), _uw_ldr_x_post(10, 11, 16), _uw_cmp_x(10, 15), ('b.cond', _c_eq, 'squeeze'), _uw_subs_w(13, 13, 1), ('b', 0, 'scan'),
             ('label', 'new'), _uw_stp_x(15, 16, 11, 0), _uw_add_w(12, 12, 1), _uw_str_w(12, 14, o + 0x204),
             ('label', 'squeeze'), _uw_ldr_w(13, 14, o + 4), ('cbz', 13, 'end'), _uw_dup_4s(17, 13), _uw_fmul_4s(1, 1, 17),
             _uw_ldr_w(12, 14, o + 0x1c), ('cbz', 12, 'end'), _uw_add_x(11, 14, o + 0x20),
             ('label', 'find'), _uw_ldr_x_post(10, 11, 16), _uw_cmp_x(10, 16), ('b.cond', _c_eq, 'found'), _uw_subs_w(12, 12, 1), ('b.cond', _c_ne, 'find'), ('b', 0, 'end'),
             ('label', 'found'), _uw_ldur_s(16, 11, -8), _uw_ldr_s(18, 14, o + 0x18), _uw_fmul(16, 16, 18), _uw_dup_s0(18, 6), _uw_fadd(18, 18, 16), _uw_ins_s0(6, 18)]
    _uw_stub(ctx, 0x0774368, [0xad401041], body, 'ultrawide: the full-screen 2D layout squeezed into the centre 16:9 (HUD and menus undistorted)')
    # movie layer draw, after its full-target viewport (sead::Viewport at x29-40: minX +8, minY +12, maxX +16, maxY +20): shrunk to the centre 16:9 by the margin (state
    # +0x808, 0 leaves it), or, filling the wide picture (DM_UW_MOVIE_FILL), its height grown by state +0x9f0 of it on each side ((target / (16/9) - 1) / 2: the movie keeps its
    # shape, its top and bottom cut by the target's edges; 0 leaves it), then ldp x9, x8, [x19, #24]
    body = [_uw_sub_x(16, 29, 40), _uw_ldr_s(16, 16, 8), _uw_ldr_s(17, 16, 16), _uw_fsub(18, 17, 16), ('adrp', 17, ST), _uw_ldr_s(19, 17, (ST & 0xfff) + _uw + 8),
            _uw_fmul(18, 18, 19), _uw_fadd(16, 16, 18), _uw_fsub(17, 17, 18), _uw_str_s(16, 16, 8), _uw_str_s(17, 16, 16),
            _uw_ldr_s(16, 16, 12), _uw_ldr_s(17, 16, 20), _uw_fsub(18, 17, 16), _uw_ldr_s(19, 17, (ST & 0xfff) + _uw + 0x1f0),
            _uw_fmul(18, 18, 19), _uw_fsub(16, 16, 18), _uw_fadd(17, 17, 18), _uw_str_s(16, 16, 12), _uw_str_s(17, 16, 20), _uw_ldp_x(9, 8, 19, 24)]
    _uw_stub(ctx, 0x3b5c758, [0xa941a269], body, 'ultrawide: pre-rendered movies in the centre 16:9, or filling the picture')
    # NPC speech bubble anchor: mov w8, #1920.0 (layout x = ndc x * 1920) becomes 1920 / squeeze when set
    body = [('adrp', 8, ST), _uw_ldr_w(8, 8, (ST & 0xfff) + _uw + 0xc), ('cbnz', 8, 'end'), 0x52a89e08]
    _uw_stub(ctx, 0x020c2b0, [0x52a89e08], body, 'ultrawide: speech bubbles over their speaker in the squeezed layout')
    # graphics allocator setup: stp x8, x9, [sp, #16] stores the render-target pool's initial size; doubled when the target aspect is set
    body = [0xa9bf47f0, ('adrp', 16, ST), _uw_ldr_w(17, 16, (ST & 0xfff) + _uw), ('cbz', 17, 'keep'), 0xd37ff908,   # stp x16,x17,[sp,#-16]!; ...; lsl x8,x8,#1
            ('label', 'keep'), 0xa8c147f0, 0xa90127e8]   # ldp x16,x17,[sp],#16; stp x8,x9,[sp,#16]
    _uw_stub(ctx, 0x0c2a36c, [0xa90127e8], body, 'ultrawide: the render-target pool doubled for the wider targets')
    # the scene the upscaler takes in: mov x8, #1920; movk x8, #1080, lsl #32, or the state page's size
    body = [('adrp', 8, ST), _uw_ldr_x(8, 8, (ST & 0xfff) + _uw + 0x10), ('cbnz_x', 8, 'end'), 0xd280f008, 0xf2c08708]
    _uw_stub(ctx, 0x31f3a00, [0xd280f008, 0xf2c08708], body, 'ultrawide: the upscaler\'s scene size 3/4 of the picture')
    ctx.capabilities.add('ULTRAWIDE')

# Render scale (DM_RENDER_SCALE, state +0x10, dm/host/loader.c): the 3D views at that fraction of the game's own size, the dynamic resolution held at its top level (as Tears of the
# Kingdom's and Breath of the Wild's). The views' sizes come from the scale the engine stores at +0xd48 of its view-size update (str s0,[x20,#0xe5c]; v131072 main+0x31d3200, found by
# its fingerprint): the level's ResolutionReduceScale of a 2048x1152 frame, 0.75 at the top level (1536x864). That store and the size loop after it (+0xdd8, which clears the "scale
# changed" bit 3 of [x20+0xe2c]) run only in a frame where the dynamic-resolution update answers status 0, a new scale: at a steady frame rate it never does, so a stub at the store
# alone changes nothing until the game comes under load. Two stubs: at the update's answer (+0xce4, ubfx of its status byte) a host scale below 1.0 that is not yet applied (state
# +0x14, written by the second stub) makes the status 0, so that frame recomputes the sizes; at the store the game's scale is multiplied by the host's. The level stub above returns
# level 0 under such a scale, so the size is fixed: 0.5 draws 768x432. 1.0 (the loader's default) runs the game's own code. Registers and flags are kept but x8 (the status, as the
# game reads it next) and s0 (stored, and dead after the store: +0xd84 reloads it)
def _bcond(frm, to, cond): return 0x54000000 | (((to - frm) >> 2) & 0x7ffff) << 5 | cond
def _cbz_w(frm, to, rt): return 0x34000000 | (((to - frm) >> 2) & 0x7ffff) << 5 | rt

def render_scale(ctx):
    here, emit = ctx.here, ctx.emit
    fn = ctx.others.get('render scale')
    if fn is None: return   # not found in this build (a red line from the locator): the game's own sizes
    status, store = fn + 0xce4, fn + 0xd48
    ctx.site(status, '089c60d3')   # ubfx x8,x0,#32,#8: the update's status byte
    s = here(); at = lambda k: s + 4 * k   # the stub's k-th word; done is word 16
    for k, w in enumerate((
            0xd3609c08,                       # ubfx x8,x0,#32,#8     the original
            0xa9be47f0,                       # stp x16,x17,[sp,#-32]!
            0xd53b4210,                       # mrs x16,nzcv
            0xf9000bf0,                       # str x16,[sp,#16]
            ADRP(16, at(4), ctx.state),
            0xb9401211,                       # ldr w17,[x16,#0x10]  the host scale's bits
            0xb9401610,                       # ldr w16,[x16,#0x14]  the scale the store stub applied
            0x6b11021f,                       # cmp w16,w17
            _bcond(at(8), at(16), 0x0),       # b.eq done            already applied
            _cbz_w(at(9), at(16), 17),        # cbz w17,done         unset
            0x52a7f010,                       # mov w16,#0x3f800000
            0x6b10023f,                       # cmp w17,w16
            _bcond(at(12), at(16), 0x2),      # b.hs done            1.0 or more, negative or NaN: the game's own
            0x7100051f,                       # cmp w8,#1
            _bcond(at(14), at(16), 0x0),      # b.eq done            status 1, the game's other request, is left alone
            0x52800008,                       # mov w8,#0            status 0: a new scale, so the sizes are recomputed
            0xf9400bf0,                       # done: ldr x16,[sp,#16]
            0xd51b4210,                       # msr nzcv,x16
            0xa8c247f0)):                     # ldp x16,x17,[sp],#32
        assert here() == at(k); emit(w)
    emit(B(here(), status + 4))
    ctx.put(status, [B(status, s)], 'dynamic-resolution status: a host render scale not yet stored asks for new 3D sizes (state +0x10)')
    ctx.site(store, '805e0ebd')    # str s0,[x20,#0xe5c]
    s = here()   # the original is word 12
    for k, w in enumerate((
            0xadbf7ffe,                       # stp q30,q31,[sp,#-32]!
            0xa9bf47f0,                       # stp x16,x17,[sp,#-16]!
            ADRP(16, at(2), ctx.state),
            0xd53b4211,                       # mrs x17,nzcv
            0xbd40121e,                       # ldr s30,[x16,#0x10]  the host scale
            0x1e2023c8,                       # fcmp s30,#0.0
            _bcond(at(6), at(12), 0xd),       # b.le original        unset, negative or NaN
            0x1e2e101f,                       # fmov s31,#1.0
            0x1e3f23c0,                       # fcmp s30,s31
            _bcond(at(9), at(12), 0xa),       # b.ge original        1.0 or more
            0x1e3e0800,                       # fmul s0,s0,s30       the game's scale x the host's
            0xbd00161e,                       # str s30,[x16,#0x14]  applied (the status stub's test)
            0xbd0e5e80,                       # original: str s0,[x20,#0xe5c]
            0xd51b4211,                       # msr nzcv,x17
            0xa8c147f0,                       # ldp x16,x17,[sp],#16
            0xacc17ffe)):                     # ldp q30,q31,[sp],#32
        assert here() == at(k); emit(w)
    emit(B(here(), store + 4))
    ctx.put(store, [B(store, s)], 'final 3D view scale x the host render scale below 1.0 (1.0 = the game\'s own)')
    ctx.render_scale = 1



# Fixed resolution (DM_FIXED_RESOLUTION, state +0x60; its scale DM_FIXED_SCALE, state +0x64 as float bits, 0 = the game's 1.0). The engine's resolution controller
# (main+0x805b00…) reads its config flag at [x8+0x94] and, when bit 0 is clear, takes the path at main+0x80640c that renders the 3D at a fixed scale (mov w9,#0x3f800000 at
# main+0x806420, 1.0): "dynamic resolution disabled". Bit 0 set (the shipped configuration) follows the GPU-time controller, which on a Mac whose translated frame costs
# more than 16.7 ms settles at the floor (911x512 docked). The first stub takes the fixed path also when state +0x60 is set; the second gives that path the host's scale when
# state +0x64 holds one (0.5 to 1.0 as float bits), so 75 / 67 / 50 % of the top size are possible without the controller. Found as a 4-byte patch by Lichii ("Max Resolution",
# main+0x805BD0: tbz → b) and as a runtime switch by Hookshot (nx2/oot_patches.py: the flag at +0x94, the fixed path's scale); only the facts were taken.
# x16 / x17 are saved around both stubs: nothing says they are free in these functions. Neither stub touches the flags
def fixed_resolution(ctx):
    site = 0x805bd0
    ctx.site(site, 'e8410036')  # tbz w8,#0,#0x80640c
    start = ctx.here()
    ctx.emit(0xa9bf47f0)  # stp x16,x17,[sp,#-16]!
    ctx.emit(ADRP(16, ctx.here(), ctx.state))
    for word in (
        0xb9406211,  # ldr w17,[x16,#0x60]: 1 = fixed resolution
        0x35000091,  # cbnz w17,fixed (+4)
        0x36000068,  # tbz w8,#0,fixed (+3): the game's own choice
        0xa8c147f0,  # ldp x16,x17,[sp],#16
    ):
        ctx.emit(word)
    ctx.emit(B(ctx.here(), site + 4))   # dynamic: the instruction after the tbz
    ctx.emit(0xa8c147f0)  # fixed: ldp x16,x17,[sp],#16
    ctx.emit(B(ctx.here(), 0x80640c))
    ctx.put(site, [B(site, start)], 'fixed resolution: the "dynamic resolution disabled" path also when state +0x60 is set')
    site2 = 0x806420
    ctx.site(site2, '09f0a752')  # mov w9,#0x3f800000: the fixed path's scale, 1.0
    start2 = ctx.here()
    ctx.emit(0xf81f0ff0)  # str x16,[sp,#-16]!
    ctx.emit(ADRP(16, ctx.here(), ctx.state))
    for word in (
        0xb9406609,  # ldr w9,[x16,#0x64]: the host's scale as float bits (0 = unset)
        0x35000049,  # cbnz w9,done (+2)
        0x52a7f009,  # mov w9,#0x3f800000: the game's 1.0
        0xf84107f0,  # done: ldr x16,[sp],#16
    ):
        ctx.emit(word)
    ctx.emit(B(ctx.here(), site2 + 4))
    ctx.put(site2, [B(site2, start2)], 'fixed resolution: its scale from state +0x64 (0 = the game\'s 1.0)')
    ctx.fixed_resolution = 1


def v131072(ctx):   # one build, every stub: FRAME_STEP of a build takes the place of the function-matched frame step, so the frame ratio stub runs from here with its function's base
    ctx.base = 0x6e6be0
    ctx.others = {'dynamic resolution': 0x8065e0, 'dynamic resolution update': 0x805aa0, 'render scale': 0x31d3200}   # the level function and the update of this build, which the function-matched rule would find by fingerprint (dynamic_resolution, called by frame_step)
    frame_step(ctx)
    fixed_resolution(ctx)


FRAME_STEP = {'e0f3ccfaf50065ae4ea01eb5aeb13b1a': v131072}   # 1.1.1 (v131072)

MATCH_FRAME_STEP = {'main': [
    {'name': 'frame ratio from the host\'s step', 'size': 0x9b4, 'fingerprints': ['6ae2aff5344d14568e4dbaf93455e2d8278384bf892ed6c6eca87fef98fbcd1d'], 'stub': frame_step,   # v131072 main+0x6e6be0
     'others': {'dynamic resolution': {'size': 0x294, 'fingerprints': ['7af6ceb0aedf8e0c17dc08ce17fcd6a7cba6d394a0d09e3b504c6d668dc418e7']},   # v131072 main+0x8065e0
                'dynamic resolution update': {'size': 0xb24, 'fingerprints': ['5a423697838976baf286cffa5e2ceef0d4e037abbcd9d371e90e9e702d61b3d4']},   # main+0x805aa0
                'render scale': {'size': 0xfc8, 'fingerprints': ['2c1804f08798ceee012ae30a1ba6b177a6b6a61ce732185bad28e9989d05e165']}}},   # main+0x31d3200, the 3D view size update
]}

BINDING = [
    {'what': 'frame ratio from the host\'s step', 'now': 'game', 'goal': 'game', 'purpose': 'frame rate',
     'why': "the game's own frame-ratio division, found by its function's fingerprint on any build that keeps the function",
     'checked': 'v131072 main: one function with this fingerprint, the site and its free registers read by disassembly (2026-11-08)'},
    {'what': 'fixed resolution and its scale', 'now': 'build', 'goal': 'game', 'purpose': 'rendering',
     'why': "the resolution controller's config flag and the fixed path's scale constant",
     'blocked': 'the flag read and the scale constant are verified for this main build only',
     'checked': 'v131072 main E0F3CCFAF50065AE4EA01EB5AEB13B1A, the tbz at +0x805bd0 and the fixed path at +0x80640c read by disassembly (2026-11-08)'},
    {'what': 'dynamic resolution: full size, or a climb on the load measured at each level', 'now': 'game', 'goal': 'game', 'purpose': 'rendering',
     'why': "the game's own dynamic-resolution level function and update, found by their functions' fingerprints on any build that keeps both; switchable (DM_DYNAMIC_RESOLUTION)",
     'checked': 'v131072 main: one function with each fingerprint (the level function a leaf, x2..x11 / x16 / x17 / s0..s2 free), its callers, the update and the controller fields read by disassembly, the fields read in play (2026-11-08); the climb run natively against a model of the update and in play to full size (2026-11-09)'},
    {'what': 'render scale: the 3D views at a fraction of the game\'s own size (DM_RENDER_SCALE)', 'now': 'game', 'goal': 'game', 'purpose': 'rendering',
     'why': "the game's own view-size update (its test of the dynamic-resolution status and its scale store), found by its function's fingerprint on any build that keeps it; the level function's stub above holds level 0 under a scale",
     'checked': 'v131072 main: one function with this fingerprint (main+0x31d3200, 0xfc8 bytes); the status ubfx at +0xce4, the store at +0xd48 (s0 computed there from the update\'s answer, fmov s0,w0 at +0xd34, never reread from +0xe5c) and the size loop that clears bit 3 of +0xe2c read by disassembly (2026-11-09)'},
    {'what': 'native output: the window crop\'s two 80 % multiplies skipped (DM_OUTPUT=native)', 'now': 'build', 'goal': 'game', 'purpose': 'rendering',
     'why': "two multiplies in v131072's crop function, placed by address and only when the frame-step function sits at v131072's place; a function-matched rule could carry them to other builds",
     'checked': 'v131072 main: the sites and x16 read by disassembly; the same skip (both multiplies as no-ops) run headless in Castle Town at 3024x1702 and checked for speech bubbles and button prompts (M5 Max, macOS 26.6.2, 2026-11-09)'},
    {'what': 'render size: the docked output and render size, the display mode\'s 2560x1440 entry and the float output size from the state page', 'now': 'build', 'goal': 'game', 'purpose': 'rendering',
     'why': "five fixed 2560x1440 constants in v131072's main (the sites PR #1460 found for its ultrawide cuts), placed by address and only when the frame-step function sits at v131072's place; a function-matched rule could carry them to other builds",
     'checked': 'v131072 headless at 2560x1440 and 3840x2160 (swapchain at the size, no crash, 60 fps held), in play at 2560x1440 and 3024x1702 (M5 Max, macOS 26.6.2, 2026-11-08 and 09)'},
]
