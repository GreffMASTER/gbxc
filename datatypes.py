from struct import pack
from typing import BinaryIO
import base64


class LookBackStrHolder:
    has_been_used = False
    lookback_strings = []
    version = 3


lookback = LookBackStrHolder()


def reset_lookback():
    lookback.has_been_used = False
    lookback.lookback_strings = []


def __write_skip(file_w: BinaryIO, value: str, params=None):
    file_w.write(b'PIKS')


def __write_raw(file_w: BinaryIO, value: str, params=None):
    try:
        value = bytes(value, 'utf-8')
    except ValueError:
        print(f'Data type tag error: incorrect text value "{value}" in <raw> tag!')
        return 1

    file_w.write(value)
    return 0


def __write_b64(file_w: BinaryIO, value: str, params=None):
    data = None
    try:
        data = base64.standard_b64decode(value)
    except Exception:
        print("Data type tag error: incorrect text value in <b64> tag!")
        return 1

    file_w.write(data)
    return 0


def __write_bool(file_w: BinaryIO, value: str, params=None):
    try:
        value = int(value)
    except ValueError:
        print(f'Data type tag error: incorrect text value "{value}" in <bool> tag!')
        return 1

    if value > 0:
        file_w.write(pack('<I', 1))
    else:
        file_w.write(pack('<I', 0))
    return 0


def __write_byte(file_w: BinaryIO, value: str, params=None):
    try:
        value = int(value)
    except ValueError:
        print(f'Data type tag error: incorrect text value "{value}" in <byte>/<uint8> tag!')
        return 1

    file_w.write(pack('<B', value))
    return 0


def __write_uint16(file_w: BinaryIO, value: str, params=None):
    try:
        value = int(value)
    except ValueError:
        print(f'Data type tag error: incorrect text value "{value}" in <uint16> tag!')
        return 1
    file_w.write(pack('<H', value))
    return 0


def __write_uint32(file_w: BinaryIO, value: str, params=None):
    try:
        value = int(value)
    except ValueError:
        print(f'Data type tag error: incorrect text value "{value}" in <uint32> tag!')
        return 1

    file_w.write(pack('<I', value))
    return 0


def __write_float(file_w: BinaryIO, value: str, params=None):
    try:
        value = float(value)
    except ValueError:
        print(f'Data type tag error: incorrect text value "{value}" in <float> tag!')
        return 1

    file_w.write(pack('<f', value))
    return 0


def __write_vec2(file_w: BinaryIO, value: str, params=None):
    values: list = value.split(' ')
    if len(values) != 2:
        print(f'Data type tag error: incorrect text value "{value}" in <vec2> tag!')
        return 1

    for i in range(2):
        try:
            values[i] = float(values[i])
        except ValueError:
            print(f'Data type tag error: incorrect text value "{value}" in <vec2> tag!')
            return 1
        file_w.write(pack('<f', values[i]))

    return 0


def __write_vec3(file_w: BinaryIO, value: str, params=None):
    values: list = value.split(' ')
    if len(values) != 3:
        print(f'Data type tag error: incorrect text value "{value}" in <vec3> tag!')
        return 1

    for i in range(3):
        try:
            values[i] = float(values[i])
        except ValueError:
            print(f'Data type tag error: incorrect text value "{value}" in <vec3> tag!')
            return 1
        file_w.write(pack('<f', values[i]))


def __write_vec4(file_w: BinaryIO, value: str, params=None):
    values: list = value.split(' ')
    if len(values) != 4:
        print(f'Data type tag error: incorrect text value "{value}" in <vec4> tag!')
        return 1

    for i in range(4):
        try:
            values[i] = float(values[i])
        except ValueError:
            print(f'Data type tag error: incorrect text value "{value}" in <vec3> tag!')
            return 1
        file_w.write(pack('<f', values[i]))


def __write_str(file_w: BinaryIO, value: str, params: dict):
    if not value:
        file_w.write(pack('<I', 0))
        return 0
    file_w.write(pack('<I', len(value)))
    try:
        value = bytes(value, 'utf-8')
    except ValueError:
        print(f'Data type tag error: incorrect text value "{value}" in <str> tag!')
        return 1

    file_w.write(value)
    return 0


def __write_lookbackstr(file_w: BinaryIO, value: str, params: dict):
    if params is None:
        params = {}
    if not lookback.has_been_used:
        file_w.write(pack('<I', lookback.version))
        lookback.has_been_used = True
    if not value and 'zero' not in params:
        file_w.write(pack('<I', 0xFFFFFFFF))
        return 0
    if 'zero' in params:
        value = ''

    count = 0
    index = 0
    for lookbackstr in lookback.lookback_strings:
        count += 1
        if lookbackstr == value:
            index = count
            break

    if params.get('isnumber'):
        print('Data type tag error: deprecated "isnumber" attribute in <lookbackstr> tag! Please use "type".')
        return 1

    typ = params.get('type')
    if not typ:
        print('Data type tag error: missing "type" attribute in <lookbackstr> tag!')
        return 1

    if typ == '80':
        file_w.write(pack('<I', index | 0x80000000))
    elif typ == '40':
        file_w.write(pack('<I', index | 0x40000000))
    else:
        print(f'Data type tag error: unknown type "{typ}" in <lookbackstr> tag! (must be 40 or 80)')
        return 1
    if index == 0:
        lookback.lookback_strings.append(value)
        file_w.write(pack('<I', len(value)))
        try:
            value = bytes(value, 'utf-8')
        except ValueError:
            print(f'Data type tag error: incorrect text value "{value}" in <lookbackstr> tag!')
            return 1
        file_w.write(value)
    return 0


data_types = {
    'skip': __write_skip,
    'raw': __write_raw,
    'bool': __write_bool,
    'b64': __write_b64,
    'byte': __write_byte,
    'uint8': __write_byte,
    'uint16': __write_uint16,
    'uint32': __write_uint32,
    'float': __write_float,
    'vec2': __write_vec2,
    'vec3': __write_vec3,
    'vec4': __write_vec4,
    'color': __write_vec3,
    'str': __write_str,
    'lookbackstr': __write_lookbackstr
}
