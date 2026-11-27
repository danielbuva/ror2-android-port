// Invoke SPIRV-Tools validation for the single-file converter contract.
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string_view>
#include <vector>

#include <spirv-tools/libspirv.h>

int main(int argc, char **argv)
{
    spv_target_env environment;
    if (argc != 4 || std::string_view(argv[1]) != "--target-env" ||
        !spvParseTargetEnv(argv[2], &environment)) {
        std::cerr << "Usage: spirv-val --target-env <environment> <file>\n";
        return 2;
    }

    std::ifstream input(argv[3], std::ios::binary | std::ios::ate);
    const std::streamoff length = input.tellg();
    if (length <= 0 || length % sizeof(uint32_t) != 0) {
        std::cerr << "Cannot read a SPIR-V word stream from " << argv[3] << '\n';
        return 1;
    }
    std::vector<uint32_t> words(length / sizeof(uint32_t));
    input.seekg(0);
    if (!input.read(reinterpret_cast<char *>(words.data()), length)) {
        std::cerr << "Cannot read " << argv[3] << '\n';
        return 1;
    }

    spv_context context = spvContextCreate(environment);
    spv_diagnostic diagnostic = nullptr;
    const spv_result_t result = spvValidateBinary(context, words.data(), words.size(), &diagnostic);
    if (diagnostic)
        spvDiagnosticPrint(diagnostic);
    spvDiagnosticDestroy(diagnostic);
    spvContextDestroy(context);
    return result == SPV_SUCCESS ? 0 : 1;
}
