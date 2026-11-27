// Compile one DXBC stage with explicit descriptor bindings using Wine vkd3d.
#include <charconv>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string_view>
#include <vector>
#include <vkd3d_shader.h>

static bool unsigned_argument(std::string_view text, unsigned int &value)
{
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    return result.ec == std::errc() && result.ptr == text.data() + text.size();
}

static bool descriptor_argument(std::string_view text, vkd3d_shader_resource_binding &row)
{
    row.flags = VKD3D_SHADER_BINDING_FLAG_IMAGE;
    if (text == "cbv") {
        row.type = VKD3D_SHADER_DESCRIPTOR_TYPE_CBV;
        row.flags = VKD3D_SHADER_BINDING_FLAG_BUFFER;
    } else if (text == "sampler") {
        row.type = VKD3D_SHADER_DESCRIPTOR_TYPE_SAMPLER;
    } else if (text == "texture") {
        row.type = VKD3D_SHADER_DESCRIPTOR_TYPE_SRV;
    } else {
        return false;
    }
    return true;
}

int main(int argc, char **argv)
{
    if (argc < 3 || (argc - 3) % 4) {
        std::cerr << "usage: shader-dxbc INPUT OUTPUT [KIND REGISTER SET BINDING ...]\n";
        return 2;
    }
    std::ifstream input(argv[1], std::ios::binary);
    const std::vector<char> dxbc(std::istreambuf_iterator<char>{input}, {});
    if (!input.is_open() || input.bad() || dxbc.empty()) {
        std::cerr << "shader-dxbc: could not read DXBC input\n";
        return 1;
    }
    std::vector<vkd3d_shader_resource_binding> bindings;
    for (int i = 3; i < argc; i += 4) {
        vkd3d_shader_resource_binding row{};
        if (!descriptor_argument(argv[i], row) ||
            !unsigned_argument(argv[i + 1], row.register_index) ||
            !unsigned_argument(argv[i + 2], row.binding.set) ||
            !unsigned_argument(argv[i + 3], row.binding.binding)) {
            std::cerr << "shader-dxbc: invalid descriptor binding\n";
            return 2;
        }
        row.shader_visibility = VKD3D_SHADER_VISIBILITY_ALL;
        row.binding.count = 1;
        bindings.push_back(row);
    }

    vkd3d_shader_spirv_target_info target{};
    target.type = VKD3D_SHADER_STRUCTURE_TYPE_SPIRV_TARGET_INFO;
    target.environment = VKD3D_SHADER_SPIRV_ENVIRONMENT_VULKAN_1_0;
    vkd3d_shader_interface_info interface_info{};
    interface_info.type = VKD3D_SHADER_STRUCTURE_TYPE_INTERFACE_INFO;
    interface_info.next = &target;
    interface_info.bindings = bindings.data();
    interface_info.binding_count = static_cast<unsigned int>(bindings.size());
    vkd3d_shader_compile_info request{};
    request.type = VKD3D_SHADER_STRUCTURE_TYPE_COMPILE_INFO;
    request.next = &interface_info;
    request.source = {dxbc.data(), dxbc.size()};
    request.source_type = VKD3D_SHADER_SOURCE_DXBC_TPF;
    request.target_type = VKD3D_SHADER_TARGET_SPIRV_BINARY;
    request.source_name = argv[1];
    request.log_level = VKD3D_SHADER_LOG_WARNING;
    vkd3d_shader_code spirv{};
    char *messages = nullptr;
    const int status = vkd3d_shader_compile(&request, &spirv, &messages);
    if (messages) {
        std::cerr << messages;
        vkd3d_shader_free_messages(messages);
    }
    if (status < 0) {
        std::cerr << "shader-dxbc: compilation failed (" << status << ")\n";
        return 1;
    }
    std::ofstream output(argv[2], std::ios::binary);
    output.write(static_cast<const char *>(spirv.code), static_cast<std::streamsize>(spirv.size));
    vkd3d_shader_free_shader_code(&spirv);
    output.close();
    if (!output) {
        std::cerr << "shader-dxbc: could not write SPIR-V output\n";
        return 1;
    }
    return 0;
}
