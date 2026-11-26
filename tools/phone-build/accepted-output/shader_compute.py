"""Project fresh SDK compiler results onto the native ComputeShader type tree."""

import io
import struct


def kernel_binary(data):
    """Read the exact SDK's successful single-kernel ComputeShaderBinary."""
    stream = io.BytesIO(data)

    def take(size):
        if size > len(data) - stream.tell():
            raise ValueError("truncated SDK compute binary")
        return stream.read(size)

    def number(fmt):
        return struct.unpack("<" + fmt, take(struct.calcsize("<" + fmt)))[0]

    def string():
        return take(number("I")).decode("utf-8")

    def array(read):
        count = number("Q")
        if count > len(data) - stream.tell():
            raise ValueError("invalid SDK compute array length")
        return [read() for _ in range(count)]

    def parameter():
        return {
            "name": string(),
            "type": number("i"),
            "offset": number("I"),
            "arraySize": number("I"),
            "rowCount": number("I"),
            "colCount": number("I"),
        }

    def constant_buffer():
        return {"name": string(), "byteSize": number("i"), "params": array(parameter)}

    def resource():
        return {
            "name": string(),
            "generatedName": string(),
            "bindPoint": number("i"),
            "samplerBindPoint": number("i"),
            "texDimension": number("i"),
        }

    # The import directives are empty in a response from compileComputeKernel.
    # The following vector contains one constant-buffer table per compiled kernel.
    if number("Q") != 0 or number("I") != 0 or number("Q") != 1:
        raise ValueError("unexpected SDK compute import directives or buffer table count")
    buffers = array(constant_buffer)
    if number("Q") != 1:
        raise ValueError("unexpected SDK compute kernel count")
    name = string()
    kernel = {key: array(resource) for key in ("cbs", "textures", "inBuffers", "outBuffers")}
    kernel["builtinSamplers"] = array(lambda: {"sampler": number("I"), "bindPoint": number("i")})
    code = take(number("Q"))
    if len(code) < 20 or len(code) % 4 or not code.startswith(b"\x03\x02\x23\x07"):
        raise ValueError("SDK compute kernel lacks Vulkan SPIR-V: " + name)
    kernel["code"] = code
    kernel["threadGroupSize"] = [number("I") for _ in range(3)]
    if not all(kernel["threadGroupSize"]) or take(1) != b"\x01" or stream.read(1):
        raise ValueError("invalid SDK compute kernel workgroup or terminal status: " + name)
    return name, buffers, kernel


def compile_tree(connection, filename, name, expected_kernels, *, platform_keywords=()):
    """Compile the admitted no-keyword-axis camera kernels into renderer 21."""
    preprocessed = connection.preprocess_compute(filename.read_text(encoding="utf-8"), filename, platform_keywords=platform_keywords)
    kernels = preprocessed["kernels"]
    if [kernel["name"] for kernel in kernels] != list(expected_kernels) or preprocessed["requirements"] is None:
        raise ValueError("camera compute kernel declarations changed: " + name)
    if any(preprocessed["keywords"].values()) or preprocessed["requirement_overrides"]:
        raise ValueError("camera compute keyword variants require qualification: " + name)
    variant = {"targetRenderer": 21, "targetLevel": 0, "kernels": [], "constantBuffers": [], "resourcesResolved": True}
    for declaration in kernels:
        expected_name = declaration["name"]
        result = connection.compile_compute(
            preprocessed["source"],
            filename,
            expected_name,
            defines=declaration["defines"],
            platform_keywords=platform_keywords,
            requirements=preprocessed["requirements"],
            flags=preprocessed["flags"],
        )
        if not result["success"]:
            raise ValueError(f"camera compute compilation failed for {expected_name}: {result['diagnostics']}")
        kernel_name, buffers, kernel = kernel_binary(result["data"])
        if kernel_name != expected_name or kernel["threadGroupSize"] != expected_kernels[expected_name]:
            raise ValueError("camera compute kernel name or workgroup differs: " + expected_name)
        by_name = {buffer["name"]: buffer for buffer in buffers}
        if len(by_name) != len(buffers) or set(by_name) != {binding["name"] for binding in kernel["cbs"]}:
            raise ValueError("camera compute bindings and constant buffer definitions differ: " + expected_name)
        indices = []
        for binding in kernel["cbs"]:
            buffer = by_name[binding["name"]]
            if buffer not in variant["constantBuffers"]:
                variant["constantBuffers"].append(buffer)
            indices.append(variant["constantBuffers"].index(buffer))
        kernel.update(cbVariantIndices=indices, requirements=preprocessed["requirements"])
        variant["kernels"].append({"name": kernel_name, "variantMap": [("", kernel)], "globalKeywords": [], "localKeywords": []})
    return {"m_Name": name, "variants": [variant]}
