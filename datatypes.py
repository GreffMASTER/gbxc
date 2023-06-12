import logging
from struct import pack
from struct import error as packerr
from typing import BinaryIO
from gbxclasses import GBXClasses
import xml.etree.ElementTree as ET
from gbxerrors import GBXWriteError


class LookBackStrHolder:
    has_been_used = False
    lookback_strings = []
    version = 3


lookback = LookBackStrHolder()
gbx_classes = GBXClasses()


def reset_lookback():
    lookback.has_been_used = False
    lookback.lookback_strings = []


def __write_skip(file_w: BinaryIO, _value: str, _params=None, _element: ET.Element = None):
    file_w.write(b'PIKS')


def __write_raw(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        value = bytes(value, 'utf-8')
        file_w.write(value)
    except ValueError:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <raw> tag!')
        raise GBXWriteError


def __write_hex(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        hex_bytes = bytes.fromhex(value)
        file_w.write(hex_bytes)
    except ValueError:
        logging.error("Data type tag error: incorrect text value in <hex> tag!")
        raise GBXWriteError


def __write_bool(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        value = int(value)
        if value > 0:
            file_w.write(pack('<I', 1))
        else:
            file_w.write(pack('<I', 0))
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <bool> tag!')
        raise GBXWriteError


def __write_uint8(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        value = int(value)
        file_w.write(pack('<B', value))
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <uint8> tag!')
        raise GBXWriteError


def __write_int8(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        value = int(value)
        file_w.write(pack('<b', value))
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <int8> tag!')
        raise GBXWriteError


def __write_uint16(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        value = int(value)
        file_w.write(pack('<H', value))
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <uint16> tag!')
        raise GBXWriteError


def __write_int16(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        value = int(value)
        file_w.write(pack('<h', value))
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <int16> tag!')
        raise GBXWriteError


def __write_uint32(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        value = int(value)
        file_w.write(pack('<I', value))
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <uint32> tag!')
        raise GBXWriteError


def __write_int32(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    try:
        value = int(value)
        file_w.write(pack('<i', value))
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <int32> tag!')
        raise GBXWriteError


def __write_float(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    value = value.replace(',', '.')
    try:
        value = float(value)
        file_w.write(pack('<f', value))
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <float> tag!')
        raise GBXWriteError


def __write_vec2(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    value = value.replace(',', '.')
    values: list = value.split(' ')

    if len(values) != 2:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <vec2> tag!')
        raise GBXWriteError

    for i in range(2):
        try:
            values[i] = float(values[i])
            file_w.write(pack('<f', values[i]))
        except ValueError or packerr:
            logging.error(f'Data type tag error: incorrect text value "{value}" in <vec2> tag!')
            raise GBXWriteError


def __write_vec3(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    value = value.replace(',', '.')
    values: list = value.split(' ')

    if len(values) != 3:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <vec3> tag!')
        raise GBXWriteError

    for i in range(3):
        try:
            values[i] = float(values[i])
            file_w.write(pack('<f', values[i]))
        except ValueError or packerr:
            logging.error(f'Data type tag error: incorrect text value "{value}" in <vec3> tag!')
            raise GBXWriteError


def __write_vec4(file_w: BinaryIO, value: str, _params=None, _element: ET.Element = None):
    value = value.replace(',', '.')
    values: list = value.split(' ')

    if len(values) != 4:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <vec4> tag!')
        raise GBXWriteError

    for i in range(4):
        try:
            values[i] = float(values[i])
            file_w.write(pack('<f', values[i]))
        except ValueError or packerr:
            logging.error(f'Data type tag error: incorrect text value "{value}" in <vec4> tag!')
            raise GBXWriteError


def __write_str(file_w: BinaryIO, value: str, _params: dict, _element: ET.Element = None):
    if not value:
        file_w.write(pack('<I', 0))
        return
    try:
        file_w.write(pack('<I', len(value)))
        value = bytes(value, 'utf-8')
        file_w.write(value)
    except ValueError or packerr:
        logging.error(f'Data type tag error: incorrect text value "{value}" in <str> tag!')
        raise GBXWriteError


def __write_lookbackstr(file_w: BinaryIO, value: str, params: dict, _element: ET.Element = None):
    if params is None:
        params = {}
    if not lookback.has_been_used:
        file_w.write(pack('<I', lookback.version))
        lookback.has_been_used = True
    if not value and 'zero' not in params:
        file_w.write(pack('<I', 0xFFFFFFFF))
        return
    if 'zero' in params:
        value = ''

    count = 0
    index = 0
    for lookbackstr in lookback.lookback_strings:
        count += 1
        if lookbackstr == value:
            index = count
            break

    typ = params.get('type')
    if not typ:
        logging.error('Data type tag error: missing "type" attribute in <lookbackstr> tag!')
        raise GBXWriteError

    if typ == '80':
        file_w.write(pack('<I', index | 0x80000000))
    elif typ == '40':
        file_w.write(pack('<I', index | 0x40000000))
    else:
        logging.error(f'Data type tag error: unknown type "{typ}" in <lookbackstr> tag! (must be 40 or 80)')
        raise GBXWriteError
    if index == 0:
        lookback.lookback_strings.append(value)
        file_w.write(pack('<I', len(value)))
        try:
            value = bytes(value, 'utf-8')
        except ValueError:
            logging.error(f'Data type tag error: incorrect text value "{value}" in <lookbackstr> tag!')
            raise GBXWriteError
        file_w.write(value)


def __write_flags(file_w: BinaryIO, _value: str, params: dict, element: ET.Element = None):
    if params is None:
        params = {}

    if not params.get('bytes'):
        logging.error('Data type tag error: missing "bytes" attribute in the <flags> tag!')
        raise GBXWriteError

    flags_bytes_str = params.get('bytes')
    flags_bytes: int

    try:
        flags_bytes = int(flags_bytes_str)
        if flags_bytes <= 0:
            logging.error(f'Data type tag error: incorrect attribute value "{flags_bytes_str}" in <flags> tag! Must be >0.')
            raise GBXWriteError
    except ValueError:
        logging.error(f'Data type tag error: incorrect attribute value "{flags_bytes_str}" in <flags> tag!')
        raise GBXWriteError

    max_bits = flags_bytes * 8
    flags_value = 0

    for flag in element:
        if flag.tag != 'flag':
            logging.error('Data type tag error: <flags> must only contain <flag> child tags!')
            raise GBXWriteError

        flag_bit = flag.get('bit')
        if not flag_bit:
            logging.error('Data type tag error: missing "bit" attribute in <flag> tag!')
            raise GBXWriteError

        bit_str = flag.get('bit')
        try:
            bit_num = int(bit_str)
            if bit_num <= 0:
                logging.error(f'Data type tag error: incorrect attribute value "{bit_str}" in <flag> tag!'
                      f'Must be >0!')
                raise GBXWriteError
            if bit_num > max_bits:
                logging.error(
                    f'Data type tag error: incorrect attribute value "{bit_str}" in <flag> tag!'
                    f'Must be <{max_bits + 1}!')
                raise GBXWriteError

            flags_value = flags_value | (1 << bit_num - 1)
        except ValueError:
            logging.error(f'Data type tag error: incorrect attribute value "{bit_str}" in <flag> tag!')
            raise GBXWriteError

    flags_data = flags_value.to_bytes(flags_bytes, 'little')
    file_w.write(flags_data)


def __write_gbxclass(file_w: BinaryIO, value: str, params: dict, _element: ET.Element = None):
    comp_lvl = params.get('complvl')
    class_id = params.get('id')

    try:
        gbx_classes.set_comp_lvl(int(comp_lvl))
    except ValueError:
        pass

    if value in gbx_classes.get_dict():
        full_class_id = gbx_classes.get_dict().get(value)
        if class_id:
            full_class_id = f'{full_class_id[:-3]}{class_id}'
        try:
            file_w.write(pack('<I', int(full_class_id, 16)))
        except ValueError:
            raise GBXWriteError
    else:
        logging.error(f'Data type tag error: could not find class of the name "{value}"!')
        raise GBXWriteError


data_types = {
    'skip': __write_skip,
    'raw': __write_raw,
    'hex': __write_hex,
    'bool': __write_bool,
    'uint8': __write_uint8,
    'int8': __write_int8,
    'uint16': __write_uint16,
    'int16': __write_int16,
    'uint32': __write_uint32,
    'int32': __write_int32,
    'float': __write_float,
    'vec2': __write_vec2,
    'vec3': __write_vec3,
    'vec4': __write_vec4,
    'color': __write_vec3,
    'str': __write_str,
    'lookbackstr': __write_lookbackstr,
    'flags': __write_flags,
    'gbxclass': __write_gbxclass
}
