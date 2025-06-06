from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import copy, get, rmdir, replace_in_file
from conan.tools.layout import basic_layout
from conan.tools.scm import Version
import os

required_conan_version = ">=2"


class BitserializerConan(ConanFile):
    name = "bitserializer"
    description = "Multi-format serialization library (JSON, XML, YAML, CSV, MsgPack)"
    topics = ("serialization", "json", "xml", "yaml", "csv", "msgpack")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/PavelKisliak/BitSerializer"
    license = "MIT"
    package_type = "header-library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "fPIC": [True, False],
        "with_cpprestsdk": [True, False],
        "with_rapidjson": [True, False],
        "with_pugixml": [True, False],
        "with_rapidyaml": [True, False],
        "with_csv": [True, False],
        "with_msgpack": [True, False],
    }
    default_options = {
        "fPIC": True,
        "with_cpprestsdk": False,
        "with_rapidjson": False,
        "with_pugixml": False,
        "with_rapidyaml": False,
        "with_csv": False,
        "with_msgpack": False,
    }

    @property
    def _compilers_minimum_version(self):
        return {
            "gcc": "8",
            "clang": "8",
            "Visual Studio": "15",
            "msvc": "191",
            "apple-clang": "12",
        }

    def _is_header_only(self, info=False):
        # All components of library are header-only except csv-archive and msgpack-archive
        options = self.info.options if info else self.options
        return not (options.with_csv or options.get_safe("with_msgpack"))

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        if Version(self.version) < "0.70":
            del self.options.with_msgpack
        # The component based on CppRestSdk has been removed since version 0.80
        if Version(self.version) >= "0.80":
            del self.options.with_cpprestsdk

    def configure(self):
        if self._is_header_only():
            self.options.rm_safe("fPIC")
        else:
            self.package_type = "static-library"

    def layout(self):
        if self._is_header_only():
            basic_layout(self, src_folder="src")
        else:
            cmake_layout(self, src_folder="src")

    def requirements(self):
        if self.options.get_safe("with_cpprestsdk"):
            self.requires("cpprestsdk/2.10.19", transitive_headers=True, transitive_libs=True)
        if self.options.get_safe("with_rapidjson"):
            self.requires("rapidjson/1.1.0", transitive_headers=True, transitive_libs=True)
        if self.options.get_safe("with_pugixml"):
            self.requires("pugixml/1.15", transitive_headers=True, transitive_libs=True)
        if self.options.get_safe("with_rapidyaml"):
            required_rapidyaml = "rapidyaml/0.8.0" if Version(self.version) >= "0.80" else "rapidyaml/0.5.0"
            self.requires(required_rapidyaml, transitive_headers=True, transitive_libs=True)

    def package_id(self):
        if self._is_header_only(info=True):
            self.info.clear()

    def validate(self):
        check_min_cppstd(self, 17)

        minimum_version = self._compilers_minimum_version.get(str(self.settings.compiler), False)
        if minimum_version and Version(self.settings.compiler.version) < minimum_version:
            raise ConanInvalidConfiguration(
                f"{self.ref} requires at least {self.settings.compiler} {minimum_version}.",
            )

        # Check stdlib ABI compatibility
        compiler_name = str(self.settings.compiler)
        if compiler_name == "gcc" and self.settings.compiler.libcxx != "libstdc++11":
            raise ConanInvalidConfiguration(f'Using {self.ref} with GCC requires "compiler.libcxx=libstdc++11"')
        elif compiler_name == "clang" and self.settings.compiler.libcxx not in ["libstdc++11", "libc++"]:
            raise ConanInvalidConfiguration(f'Using {self.ref} with Clang requires either "compiler.libcxx=libstdc++11"'
                                            ' or "compiler.libcxx=libc++"')

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        self._patch_sources()

    def generate(self):
        if not self._is_header_only():
            tc = CMakeToolchain(self)
            tc.cache_variables["BUILD_CPPRESTJSON_ARCHIVE"] = self.options.get_safe("with_cpprestsdk")
            tc.cache_variables["BUILD_RAPIDJSON_ARCHIVE"] = self.options.get_safe("with_rapidjson")
            tc.cache_variables["BUILD_PUGIXML_ARCHIVE"] = self.options.get_safe("with_pugixml")
            tc.cache_variables["BUILD_RAPIDYAML_ARCHIVE"] = self.options.get_safe("with_rapidyaml")
            tc.cache_variables["BUILD_CSV_ARCHIVE"] = self.options.get_safe("with_csv")
            tc.cache_variables["BUILD_MSGPACK_ARCHIVE"] = self.options.get_safe("with_msgpack")
            tc.generate()
            deps = CMakeDeps(self)
            deps.generate()

    def _patch_sources(self):
        # Remove 'ryml' subdirectory from #include
        replace_in_file(
            self,
            os.path.join(self.source_folder, "include", "bitserializer", "rapidyaml_archive.h"),
            "#include <ryml/" if Version(self.version) < "0.80" else "#include \"ryml/",
            "#include <" if Version(self.version) < "0.80" else "#include \"",
        )

    def build(self):
        if not self._is_header_only():
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

    def package(self):
        if not self._is_header_only():
            cmake = CMake(self)
            cmake.install()
            rmdir(self, os.path.join(self.package_folder, "share"))
        else:
            copy(self, "*.h", src=os.path.join(self.source_folder, "include"), dst=os.path.join(self.package_folder, "include"))
        # Copy license
        copy(self, "license.txt", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        lib_suffix = "d" if self.settings.build_type == "Debug" else ""
        self.cpp_info.set_property("cmake_file_name", "bitserializer")

        # cpprestjson-core
        self.cpp_info.components["bitserializer-core"].set_property("cmake_target_name", "BitSerializer::core")
        self.cpp_info.components["bitserializer-core"].bindirs = []
        self.cpp_info.components["bitserializer-core"].libdirs = []
        if self.settings.compiler == "gcc" or (self.settings.os == "Linux" and self.settings.compiler == "clang"):
            if Version(self.settings.compiler.version) < 9:
                self.cpp_info.components["bitserializer-core"].system_libs = ["stdc++fs"]

        # cpprestjson-archive
        if self.options.get_safe("with_cpprestsdk"):
            self.cpp_info.components["bitserializer-cpprestjson"].set_property("cmake_target_name", "BitSerializer::cpprestjson-archive")
            self.cpp_info.components["bitserializer-cpprestjson"].bindirs = []
            self.cpp_info.components["bitserializer-cpprestjson"].libdirs = []
            self.cpp_info.components["bitserializer-cpprestjson"].requires = ["bitserializer-core", "cpprestsdk::cpprestsdk"]

        # rapidjson-archive
        if self.options.get_safe("with_rapidjson"):
            self.cpp_info.components["bitserializer-rapidjson"].set_property("cmake_target_name", "BitSerializer::rapidjson-archive")
            self.cpp_info.components["bitserializer-rapidjson"].bindirs = []
            self.cpp_info.components["bitserializer-rapidjson"].libdirs = []
            self.cpp_info.components["bitserializer-rapidjson"].requires = ["bitserializer-core", "rapidjson::rapidjson"]

        # pugixml-archive
        if self.options.get_safe("with_pugixml"):
            self.cpp_info.components["bitserializer-pugixml"].set_property("cmake_target_name", "BitSerializer::pugixml-archive")
            self.cpp_info.components["bitserializer-pugixml"].bindirs = []
            self.cpp_info.components["bitserializer-pugixml"].libdirs = []
            self.cpp_info.components["bitserializer-pugixml"].requires = ["bitserializer-core", "pugixml::pugixml"]

        # rapidyaml-archive
        if self.options.get_safe("with_rapidyaml"):
            self.cpp_info.components["bitserializer-rapidyaml"].set_property("cmake_target_name", "BitSerializer::rapidyaml-archive")
            self.cpp_info.components["bitserializer-rapidyaml"].bindirs = []
            self.cpp_info.components["bitserializer-rapidyaml"].libdirs = []
            self.cpp_info.components["bitserializer-rapidyaml"].requires = ["bitserializer-core", "rapidyaml::rapidyaml"]

        # csv-archive
        if self.options.get_safe("with_csv"):
            self.cpp_info.components["bitserializer-csv"].set_property("cmake_target_name", "BitSerializer::csv-archive")
            self.cpp_info.components["bitserializer-csv"].requires = ["bitserializer-core"]
            self.cpp_info.components["bitserializer-csv"].bindirs = []
            self.cpp_info.components["bitserializer-csv"].libs = [f"csv-archive{lib_suffix}" if Version(self.version) < "0.80" else f"bitserializer-csv{lib_suffix}"]

        # msgpack-archive
        if self.options.get_safe("with_msgpack"):
            self.cpp_info.components["bitserializer-msgpack"].set_property("cmake_target_name", "BitSerializer::msgpack-archive")
            self.cpp_info.components["bitserializer-msgpack"].requires = ["bitserializer-core"]
            self.cpp_info.components["bitserializer-msgpack"].bindirs = []
            self.cpp_info.components["bitserializer-msgpack"].libs = [f"msgpack-archive{lib_suffix}" if Version(self.version) < "0.80" else f"bitserializer-msgpack{lib_suffix}"]
