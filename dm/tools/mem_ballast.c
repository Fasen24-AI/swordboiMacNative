// mem_ballast <MB> [seconds]: holds <MB> of memory the system can neither compress nor page out (random bytes, wired with mlock) until it is killed, the file named by BALLAST_STOP
// appears (default ./ballast.stop) or <seconds> pass (default 600). While it runs, a game and everything else on the Mac have that much less memory to live in: a way to see how a
// game behaves on a smaller Mac without owning one (Ocarina of Time's note, Memory: 8192 on a 24 GB Mac for a 16 GB one). What it does not copy: Metal's recommended working set and
// hw.memsize still say what the Mac has, so a host threshold derived from them must be given the smaller Mac's value by hand (DM_NVN_ALIAS_KEEP_MB). It stops the game's own Mac from
// doing anything else comfortably: keep the time short. Build: cc -O2 -o mem_ballast dm/tools/mem_ballast.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/mman.h>
#include <sys/stat.h>

int main(int argc, char **argv) {
    long mb = argc > 1 ? atol(argv[1]) : 0, secs = argc > 2 ? atol(argv[2]) : 600;
    if (mb < 256 || mb > 12288) { fprintf(stderr, "mem_ballast <MB, 256 to 12288> [seconds]\n"); return 2; }
    const char *stop = getenv("BALLAST_STOP"); if (!stop) stop = "ballast.stop";
    enum { CHUNK = 256 };
    long n = mb / CHUNK, wired = 0, held = 0;
    for (long i = 0; i < n; i++) {
        size_t len = (size_t)CHUNK << 20;
        void *p = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_ANON | MAP_PRIVATE, -1, 0);
        if (p == MAP_FAILED) { perror("mmap"); break; }
        arc4random_buf(p, len);   // random bytes: the compressor gains nothing on them
        held += CHUNK;
        if (!mlock(p, len)) wired += CHUNK;   // wired: not paged out either
    }
    printf("mem_ballast: %ld MB held, %ld MB of them wired, for %ld s (stop: %s)\n", held, wired, secs, stop); fflush(stdout);
    time_t t0 = time(NULL); struct stat st;
    while (time(NULL) - t0 < secs && stat(stop, &st)) sleep(1);
    printf("mem_ballast: released after %ld s\n", (long)(time(NULL) - t0));
    return 0;
}
