# Copyright 2024 ByteDance and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from torch.utils.cpp_extension import load


def _find_gcc12():
    import shutil
    for candidate in ("/usr/bin/gcc-12", "/usr/local/bin/gcc-12"):
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("gcc-12")


def compile(name, sources, extra_include_paths, build_directory):
    os.environ["TORCH_CUDA_ARCH_LIST"] = "7.0;8.0"
    # Use the CUDA 12.1 toolkit (matching the ppiflow torch build) to avoid
    # nvcc/header incompatibilities when a newer CUDA is the system default.
    cuda_121 = "/usr/local/cuda-12.1"
    if os.path.isdir(cuda_121):
        os.environ["CUDA_HOME"] = cuda_121
        os.environ["CUDA_PATH"] = cuda_121
    # CUDA 12.1 nvcc requires gcc ≤ 12; use gcc-12 if available.
    gcc12 = _find_gcc12()
    ccbin_flags = ["-ccbin", gcc12] if gcc12 else []
    return load(
        name=name,
        sources=sources,
        extra_include_paths=extra_include_paths,
        extra_cflags=[
            "-O3",
            "-DVERSION_GE_1_1",
            "-DVERSION_GE_1_3",
            "-DVERSION_GE_1_5",
        ],
        extra_cuda_cflags=ccbin_flags + [
            "-O3",
            "--use_fast_math",
            "-DVERSION_GE_1_1",
            "-DVERSION_GE_1_3",
            "-DVERSION_GE_1_5",
            "-std=c++17",
            "-maxrregcount=50",
            "-U__CUDA_NO_HALF_OPERATORS__",
            "-U__CUDA_NO_HALF_CONVERSIONS__",
            "--expt-relaxed-constexpr",
            "--expt-extended-lambda",
            "-gencode",
            "arch=compute_70,code=sm_70",
            "-gencode",
            "arch=compute_80,code=sm_80",
            "-gencode",
            "arch=compute_86,code=sm_86",
            "-gencode",
            "arch=compute_90,code=sm_90",
        ],
        verbose=True,
        build_directory=build_directory,
    )
