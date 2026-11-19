// Decode a Basis Universal image from stdin to an RGB PPM on stdout.
// Build with the pinned Basis Universal transcoder, without its encoder.
#include "basisu_transcoder.h"
#include <cstdint>
#include <iostream>
#include <iterator>
#include <vector>

int main() {
    std::cin.sync_with_stdio(false);
    std::vector<char> input(std::istreambuf_iterator<char>(std::cin), {});
    basist::basisu_transcoder_init();
    basist::basisu_transcoder decoder;
    basist::basisu_image_level_info info{};
    if (input.size() > UINT32_MAX ||
        !decoder.get_image_level_info(input.data(), input.size(), info, 0, 0) ||
        !decoder.start_transcoding(input.data(), input.size())) {
        std::cerr << "Invalid Basis image\n";
        return 1;
    }
    const uint32_t pixels = info.m_orig_width * info.m_orig_height;
    if (!pixels || pixels > 64 * 1024 * 1024) {
        std::cerr << "Unsupported image size\n";
        return 1;
    }
    std::vector<uint8_t> rgba(size_t(pixels) * 4), rgb(size_t(pixels) * 3);
    if (!decoder.transcode_image_level(input.data(), input.size(), 0, 0,
                                      rgba.data(), pixels, basist::transcoder_texture_format::cTFRGBA32)) {
        std::cerr << "Basis decode failed\n";
        return 1;
    }
    for (size_t i = 0; i < pixels; ++i)
        for (size_t channel = 0; channel < 3; ++channel)
            rgb[i * 3 + channel] = rgba[i * 4 + channel];
    std::cout << "P6\n" << info.m_orig_width << " " << info.m_orig_height << "\n255\n";
    std::cout.write(reinterpret_cast<const char*>(rgb.data()), rgb.size());
    return std::cout ? 0 : 1;
}
