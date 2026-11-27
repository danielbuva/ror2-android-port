// Encode one SPIR-V stage using the public SMOL-V codec.
#include <iostream>
#include <iterator>
#include <smolv.h>

int main()
{
    std::ios::sync_with_stdio(false);
    const smolv::ByteArray spirv(std::istreambuf_iterator<char>{std::cin}, {});
    smolv::ByteArray encoded;
    if (std::cin.bad() || spirv.empty() || !smolv::Encode(spirv.data(), spirv.size(), encoded)) {
        std::cerr << "shader-smolv: could not encode SPIR-V input\n";
        return 1;
    }
    std::cout.write(reinterpret_cast<const char *>(encoded.data()), static_cast<std::streamsize>(encoded.size()));
    std::cout.flush();
    if (!std::cout) {
        std::cerr << "shader-smolv: could not write encoded stage\n";
        return 1;
    }
    return 0;
}
