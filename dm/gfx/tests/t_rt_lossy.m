// Unsupported lossy descriptors abort in Metal instead of returning nil: eligibility
// must be decided before allocation, and the default path must remain lossless.
#include "../nvn/nvn_mtl.m"
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }
static int checks, failed;
#define CHECK(c, label) do { checks++; if (!(c)) { failed++; fprintf(stderr, "FAIL: %s\n", label); } } while (0)


static tex_t target(pool_t *p, unsigned format, unsigned flags, uint64_t serial) {
    tex_t t = {.magic = MAGIC('T','E','X',0), .pool = p, .serial = serial, .off = (int64_t)(serial % 128) * (2 << 20)};
    t.mem = p->mem + t.off;
    t.d = (nvn_texdesc){.target = NVN_TEXTURE_TARGET_2D, .format = format, .flags = flags,
        .width = 512, .height = 512, .depth = 1, .levels = 1, .samples = 1};
    nvn_tex_layout(&t.d, &t.L); mtl_tex_init(&t); return t;
}
int main(int argc, char **argv) { @autoreleasepool {
    int on = argc == 1;
    if (on) setenv("DM_NVN_RT_LOSSY", "1", 1); else unsetenv("DM_NVN_RT_LOSSY");
    setenv("DM_NVN_POOL_HEAP", "0", 1); setenv("DM_NVN_RT_RECYCLE", "0", 1);
    mtl_init();
    if (![g_dev supportsFamily:MTLGPUFamilyApple8]) { puts("SKIP: lossy compression needs Apple8"); return 0; }
    MTLTextureDescriptor *valid = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:512 height:512 mipmapped:NO];
    valid.storageMode = MTLStorageModePrivate; valid.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    rt_lossy_apply(valid);
    id<MTLTexture> bgra = [g_dev newTextureWithDescriptor:valid];
    CHECK(bgra && bgra.compressionType == (on ? MTLTextureCompressionTypeLossy : MTLTextureCompressionTypeLossless), "the measured BGRA8 format is supported");
    for (int k = 0; k < 11; k++) {
        MTLTextureDescriptor *d = [valid copy]; d.compressionType = MTLTextureCompressionTypeLossless;
        switch (k) {
            case 0: d.storageMode = MTLStorageModeShared; break;
            case 1: d.allowGPUOptimizedContents = NO; break;
            case 2: d.usage |= MTLTextureUsageShaderWrite; break;
            case 3: d.usage |= MTLTextureUsageShaderAtomic; break;
            case 4: d.usage |= MTLTextureUsagePixelFormatView; break;
            case 5: d.usage = MTLTextureUsageShaderRead; break;
            case 6: d.textureType = MTLTextureType1D; break;
            case 7: d.textureType = MTLTextureType1DArray; break;
            case 8: d.textureType = MTLTextureTypeTextureBuffer; break;
            case 9: d.pixelFormat = MTLPixelFormatBC1_RGBA; break;
            case 10: d.pixelFormat = MTLPixelFormatASTC_4x4_LDR; break;
        }
        rt_lossy_apply(d);
        CHECK(d.compressionType == MTLTextureCompressionTypeLossless, "unsupported usage, storage, type and formats never select lossy");
    }
    pool_t p = {.magic = MAGIC('P','O','O','L'), .flags = NVN_MEMORY_POOL_FLAGS_CPU_NO_ACCESS | NVN_MEMORY_POOL_FLAGS_VIRTUAL,
        .size = 256 << 20, .vmode = 1};
    p.mem = aligned_alloc(16384, p.size);
    unsigned formats[] = {NVN_FORMAT_R8, NVN_FORMAT_R32F, NVN_FORMAT_RG16F,
        NVN_FORMAT_RGBA8, NVN_FORMAT_RGBA8_SRGB, NVN_FORMAT_RGB10A2, NVN_FORMAT_RGBA16F};
    mtl_sub_begin();
    for (unsigned i = 0; i < sizeof formats / sizeof *formats; i++) {
        tex_t t = target(&p, formats[i], NVN_TEXTURE_FLAGS_COMPRESSIBLE, 999000 + i);
        id<MTLTexture> mt = tex_mtl(&t);
        CHECK(mt != nil, "an allowed target is allocated");
        CHECK(mt.compressionType == (on ? MTLTextureCompressionTypeLossy : MTLTextureCompressionTypeLossless), "the actual render-target path honors the opt-in");
        MTLTextureDescriptor *d = tex_desc(&t, 0); MTLSizeAndAlign full = [g_dev heapTextureSizeAndAlignWithDescriptor:d];
        if (on) CHECK(mt.allocatedSize < full.size * 3 / 4, "lossy storage is materially smaller than lossless");
        if (formats[i] == NVN_FORMAT_RGBA8) {
            id<MTLTexture> srgb = [mt newTextureViewWithPixelFormat:MTLPixelFormatRGBA8Unorm_sRGB];
            CHECK(srgb != nil, "an sRGB twin can still read the target");
            id<MTLTexture> upgraded = tex_upgrade(&t, mt, MTLTextureUsageShaderWrite, MTLPixelFormatInvalid);
            CHECK(upgraded && (upgraded.usage & MTLTextureUsageShaderWrite), "a later shader write upgrades the target");
            CHECK(upgraded.compressionType == MTLTextureCompressionTypeLossless, "a shader-writable upgrade is lossless");
        }
    }
    unsigned excluded[] = {NVN_FORMAT_R11G11B10F, NVN_FORMAT_DEPTH32F};
    for (unsigned i = 0; i < sizeof excluded / sizeof *excluded; i++) {
        tex_t t = target(&p, excluded[i], NVN_TEXTURE_FLAGS_COMPRESSIBLE, 999020 + i);
        id<MTLTexture> mt = tex_mtl(&t);
        CHECK(mt && mt.compressionType == MTLTextureCompressionTypeLossless, "depth and packed float stay lossless without asserting");
    }
    tex_t image = target(&p, NVN_FORMAT_RGBA16F, NVN_TEXTURE_FLAGS_COMPRESSIBLE | NVN_TEXTURE_FLAGS_IMAGE, 999030);
    id<MTLTexture> im = tex_mtl(&image);
    CHECK(im && im.compressionType == MTLTextureCompressionTypeLossless, "shader-writable images stay lossless");
    tex_t a = target(&p, NVN_FORMAT_RGBA16F, NVN_TEXTURE_FLAGS_COMPRESSIBLE, 999040), b = a;
    b.serial = 999041; b.d.width = b.d.height = 256; nvn_tex_layout(&b.d, &b.L); mtl_tex_init(&b);
    id<MTLTexture> ma = tex_mtl(&a), mb = tex_mtl(&b);
    CHECK(ma.heap && ma.heap == mb.heap, "resolution-family sharing remains available");
    CHECK(!ma.allowGPUOptimizedContents && ma.compressionType == MTLTextureCompressionTypeLossless,
          "uncompressed family storage is never forced into lossy compression");
    mtl_sub_commit(); mtl_drain();
    CHECK(!mtl_last_commit_error(), "initialization and the upgrade copy finish without GPU errors");
    mtl_alias_drop_pool(&p); mtl_drain();
    printf("%d checks, %d failures\n", checks, failed); return failed != 0;
} }
