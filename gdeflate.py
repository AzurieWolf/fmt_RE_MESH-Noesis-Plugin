import ctypes
import os
import platform
from ctypes import POINTER, byref, c_bool, c_uint8, c_uint32, c_uint64

try:
	from enum import IntEnum
except:
	class IntEnum(int):
		pass


class GDeflateCompressionLevel(IntEnum):
	FASTEST = 1
	DEFAULT = 9
	BEST_RATIO = 12


class GDeflateFlags(IntEnum):
	COMPRESS_SINGLE_THREAD = 0x200


class GDeflateError(Exception):
	pass


def is_windows():
	return platform.system() == "Windows"


def is_linux():
	return platform.system() == "Linux"


class GDeflate(object):
	FASTEST = GDeflateCompressionLevel.FASTEST
	DEFAULT = GDeflateCompressionLevel.DEFAULT
	BEST_RATIO = GDeflateCompressionLevel.BEST_RATIO

	def __init__(self, dll_path=None):
		if dll_path is None:
			module_dir = os.path.dirname(os.path.abspath(__file__))
			if is_windows():
				dll_name = "GDeflateWrapper.dll"
			elif is_linux():
				dll_name = "libGDeflateWrapper.so"
			else:
				raise RuntimeError("This OS (%s) is unsupported." % platform.system())

			possible_paths = [
				os.path.join(module_dir, dll_name),
				os.path.join(os.getcwd(), dll_name),
				dll_name,
			]

			self._dll = None
			for path in possible_paths:
				try:
					self._dll = ctypes.CDLL(str(path))
					break
				except OSError:
					pass
			if self._dll is None:
				raise GDeflateError(
					"Could not find %s in any of these locations:\n- %s" %
					(dll_name, "\n- ".join([str(p) for p in possible_paths]))
				)
		else:
			try:
				self._dll = ctypes.CDLL(str(dll_path))
			except OSError as err:
				raise GDeflateError("Failed to load GDeflate DLL from %s: %s" % (dll_path, err))

		self._get_uncompressed_size_func = self._dll.gdeflate_get_uncompressed_size
		self._get_uncompressed_size_func.argtypes = [
			POINTER(c_uint8),
			c_uint64,
			POINTER(c_uint64)
		]
		self._get_uncompressed_size_func.restype = c_bool

		self._get_compress_bound = self._dll.gdeflate_get_compress_bound
		self._get_compress_bound.argtypes = [c_uint64]
		self._get_compress_bound.restype = c_uint64

		self._decompress_func = self._dll.gdeflate_decompress
		self._decompress_func.argtypes = [
			POINTER(c_uint8),
			c_uint64,
			POINTER(c_uint8),
			c_uint64,
			c_uint32
		]
		self._decompress_func.restype = c_bool

		self._compress_func = self._dll.gdeflate_compress
		self._compress_func.argtypes = [
			POINTER(c_uint8),
			POINTER(c_uint64),
			POINTER(c_uint8),
			c_uint64,
			c_uint32,
			c_uint32
		]
		self._compress_func.restype = c_bool

	def get_uncompressed_size(self, compressed_data):
		input_array = (c_uint8 * len(compressed_data))(*compressed_data)
		uncompressed_size = c_uint64(0)

		success = self._get_uncompressed_size_func(
			input_array,
			c_uint64(len(compressed_data)),
			byref(uncompressed_size)
		)

		if not success:
			raise GDeflateError("Failed to get uncompressed size")

		return uncompressed_size.value

	def decompress(self, compressed_data, num_workers=1):
		output_size = self.get_uncompressed_size(compressed_data)
		input_array = (c_uint8 * len(compressed_data))(*compressed_data)
		output_array = (c_uint8 * output_size)()

		success = self._decompress_func(
			output_array,
			c_uint64(output_size),
			input_array,
			c_uint64(len(compressed_data)),
			c_uint32(num_workers)
		)

		if not success:
			raise GDeflateError("Decompression failed")

		return bytes(output_array)

	def compress(self, data, level=GDeflateCompressionLevel.DEFAULT, flags=0):
		bounded_output_size = self._get_compress_bound(c_uint64(len(data)))
		output_size = c_uint64(bounded_output_size)
		output_array = (c_uint8 * bounded_output_size)()
		input_array = (c_uint8 * len(data))(*data)

		success = self._compress_func(
			output_array,
			byref(output_size),
			input_array,
			c_uint64(len(data)),
			c_uint32(int(level)),
			c_uint32(flags)
		)

		if not success:
			raise GDeflateError("Compression failed")

		return bytes(output_array[:output_size.value])
